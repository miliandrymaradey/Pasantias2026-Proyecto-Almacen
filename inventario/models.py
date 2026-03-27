from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
import datetime

# ==========================================
# 1. REGISTRO MAESTRO
# ==========================================
class Material(models.Model):
    # Tipos para generar EM, EA o EDC automáticamente
    TIPO_CHOICES = [
        ('EM', 'Material Consumible (EM)'),
        ('EA', 'Activo Fijo (EA)'),
        ('EDC', 'Directo al Gasto (EDC)'),
    ]
    
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código Material")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción del Material")
    tipo = models.CharField(max_length=3, choices=TIPO_CHOICES, default='EM', verbose_name="Tipo de Material")
    nro_parte = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Parte")
    unidad_medida = models.CharField(max_length=20, verbose_name="U.M.")
    ubicacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ubicación")
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Stock Actual")

    def __str__(self):
        return f"[{self.tipo}] {self.codigo} - {self.descripcion}"

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "1. Registro Maestro"


# ==========================================
# 2. TABLA PADRE: REPORTE DE RECEPCIÓN (RP)
# ==========================================
class ReporteRecepcion(models.Model):
    nro_reporte = models.CharField(max_length=20, unique=True, blank=True, verbose_name="No. Reporte (RP)")
    fecha_recepcion = models.DateField(default=timezone.now, verbose_name="Fecha de Recepción")
    
    def save(self, *args, **kwargs):
        # AUTOMATIZACIÓN DEL RP: Si no tiene número, se lo generamos
        if not self.nro_reporte:
            # Buscamos el último reporte registrado para saber qué número sigue
            ultimo_reporte = ReporteRecepcion.objects.all().order_by('id').last()
            if ultimo_reporte and ultimo_reporte.nro_reporte.startswith('RP-'):
                try:
                    # Extrae el número (ej. de RP-007 saca 7) y le suma 1
                    ultimo_numero = int(ultimo_reporte.nro_reporte.split('-')[1])
                    nuevo_numero = ultimo_numero + 1
                except ValueError:
                    nuevo_numero = 1
            else:
                nuevo_numero = 1
                
            # Formateamos con ceros a la izquierda (ej. RP-008)
            self.nro_reporte = f"RP-{nuevo_numero:03d}"
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nro_reporte} ({self.fecha_recepcion.strftime('%d/%m/%Y')})"

    class Meta:
        verbose_name = "Reporte de Recepción"
        verbose_name_plural = "2. Reportes Diarios (RP)"


# ==========================================
# 3. TABLA HIJA: CONTROL DE ENTRADA (EM/EA/EDC)
# ==========================================
class DetalleRecepcion(models.Model):
    reporte = models.ForeignKey(ReporteRecepcion, on_delete=models.CASCADE, verbose_name="Reporte (RP)")
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Material")
    
    # Este es el código EM260001 que se generará solo
    nro_control_entrada = models.CharField(max_length=20, blank=True, unique=True, verbose_name="Nro. Control (EM/EA)")
    
    nro_odc = models.CharField(max_length=50, verbose_name="Orden de Compra (ODC)")
    nro_nota_entrega = models.CharField(max_length=50, verbose_name="Nota de Entrega")
    proveedor = models.CharField(max_length=200, verbose_name="Proveedor")
    
    cantidad_solicitada = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cant. Solicitada (ODC)")
    cantidad_recibida = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cant. Recibida Física")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="U.P. (USD)")

    @property
    def observaciones(self):
        # LÓGICA DE OBSERVACIONES AUTOMÁTICAS (Como tu Excel)
        if self.cantidad_recibida == self.cantidad_solicitada:
            return "" # En blanco si llegó completo, como me indicaste
        elif self.cantidad_recibida < self.cantidad_solicitada:
            # Formato: "ITEM 1-3" (Llegaron 3 de 9, etc)
            return f"ITEM 1-{int(self.cantidad_recibida)} (Faltan {int(self.cantidad_solicitada - self.cantidad_recibida)})"
        else:
            return "EXCEDENTE"

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None
        
        # AUTOMATIZACIÓN DEL EM/EA/EDC
        if not self.nro_control_entrada:
            prefijo = self.material.tipo # Saca 'EM', 'EA' o 'EDC' del Registro Maestro
            # Extraemos los últimos 2 dígitos del año de la fecha de recepción (ej. '26' para 2026)
            año_corto = self.reporte.fecha_recepcion.strftime('%y') 
            inicio_codigo = f"{prefijo}{año_corto}" # Ej: 'EM26'
            
            # Buscamos el último código de ese año y ese prefijo (Ej. el último EM26...)
            ultimo_detalle = DetalleRecepcion.objects.filter(
                nro_control_entrada__startswith=inicio_codigo
            ).order_by('nro_control_entrada').last()

            if ultimo_detalle:
                # Extraemos los últimos 4 dígitos y le sumamos 1
                try:
                    ultimo_num = int(ultimo_detalle.nro_control_entrada[-4:])
                    nuevo_num = ultimo_num + 1
                except ValueError:
                    nuevo_num = 1
            else:
                nuevo_num = 1 # Si es el primero del año, es 1
                
            # Ensamblamos: EM + 26 + 0001 = EM260001
            self.nro_control_entrada = f"{inicio_codigo}{nuevo_num:04d}"

        super().save(*args, **kwargs)
        
        # Sumar al inventario maestro solo si es nuevo
        if es_nuevo:
            self.material.stock_actual += self.cantidad_recibida
            self.material.save()

    def __str__(self):
        return f"{self.nro_control_entrada} - {self.material.codigo}"

    class Meta:
        verbose_name = "Recepción de Material"
        verbose_name_plural = "Control de Entradas (EM/EA)"


# ==========================================
# 4. TABLA: GUÍA DE TRASLADO (Documento de Transporte)- salidas
# ==========================================
class GuiaTraslado(models.Model):
    TALADROS = [
        ('PRV-1', 'Taladro PRV-1'),
        ('PRV-3', 'Taladro PRV-3'),
        ('PRV-4', 'Taladro PRV-4'),
        ('BASE', 'Base Operativa / Otro'),
    ]

    # Datos de la Guía
    nro_guia = models.CharField(max_length=50, unique=True, blank=True, verbose_name="No. Guía (Automático)")
    fecha = models.DateField(default=timezone.now, verbose_name="Fecha")
    hora = models.TimeField(default=timezone.now, verbose_name="Hora")
    taladro_destino = models.CharField(max_length=20, choices=TALADROS, verbose_name="Destino")
    
    # Destino Físico
    direccion = models.CharField(max_length=255, verbose_name="Dirección")
    ciudad = models.CharField(max_length=100, default="MORICHAL", verbose_name="Ciudad")

    # Datos del Transportista (Camión)
    conductor = models.CharField(max_length=100, verbose_name="Conductor")
    ci_conductor = models.CharField(max_length=20, verbose_name="C.I.")
    vehiculo = models.CharField(max_length=50, verbose_name="Vehículo (Ej. CARGO)")
    color = models.CharField(max_length=30, verbose_name="Color")
    placa = models.CharField(max_length=20, verbose_name="Placa")
    marca_modelo = models.CharField(max_length=100, verbose_name="Marca / Modelo")

    # Observaciones y Firmas
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    nombre_entregado = models.CharField(max_length=100, default="Almacén El Tigre", verbose_name="Entregado por")

    def save(self, *args, **kwargs):
        # MAGIA: Generador automático del código Ej: PRV3-0015-2026
        if not self.nro_guia:
            prefijo = self.taladro_destino.replace('-', '') # PRV-3 pasa a PRV3
            año = self.fecha.strftime('%Y') # Saca el 2026
            
            # Busca la última guía de ese taladro este año
            ultima_guia = GuiaTraslado.objects.filter(
                nro_guia__startswith=f"{prefijo}-", 
                nro_guia__endswith=año
            ).order_by('id').last()

            if ultima_guia:
                try:
                    num = int(ultima_guia.nro_guia.split('-')[1]) + 1
                except ValueError:
                    num = 1
            else:
                num = 1

            # Ensambla el código final
            self.nro_guia = f"{prefijo}-{num:04d}-{año}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nro_guia} - {self.taladro_destino}"

    class Meta:
        verbose_name = "Guía de Traslado"
        verbose_name_plural = "4. Guías de Traslado"


# ==========================================
# 5. TABLA: SALIDA DE MATERIAL (El Despacho Real)
# ==========================================
class SalidaMaterial(models.Model):
    # LA FUSIÓN: Este campo conecta la Salida con la Guía. Es OPCIONAL (null=True, blank=True)
    guia = models.ForeignKey(GuiaTraslado, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="¿Va en alguna Guía?")
    
    # Datos de la salida
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Material a Despachar")
    fecha_despacho = models.DateField(default=timezone.now, verbose_name="Fecha de Despacho")
    nro_rim = models.CharField(max_length=50, verbose_name="No. RIM (Requisición)")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad Despachada")

    def clean(self):
        # Validar que no saquen más de lo que hay
        if self.pk is None: 
            if self.cantidad > self.material.stock_actual:
                raise ValidationError({'cantidad': f"Falta Stock. Solo quedan: {self.material.stock_actual}"})

    def save(self, *args, **kwargs):
        # Descontar del inventario maestro automáticamente
        es_nuevo = self.pk is None
        super().save(*args, **kwargs)
        if es_nuevo:
            self.material.stock_actual -= self.cantidad
            self.material.save()

    def __str__(self):
        return f"RIM: {self.nro_rim} - {self.material.codigo}"

    class Meta:
        verbose_name = "Despacho RIM"
        verbose_name_plural = "3. Relación de Despachos (RIM)"