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
        ('MATERIAL', 'MATERIAL'),
        ('ACTIVOS', 'ACTIVOS'),
        ('DIRECTO AL GASTO', 'DIRECTO AL GASTO'),
    ]
    
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código Material")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción del Material")
    # Ampliamos el max_length a 20 para que quepa la palabra "DIRECTO AL GASTO"
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='MATERIAL', verbose_name="Tipo de Material")
    nro_parte = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Parte")
    unidad_medida = models.CharField(max_length=20, verbose_name="U.M.")
    ubicacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ubicación")
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Stock Actual")

# ... (tus campos existentes de la clase Material) ...

    # 1. Función para calcular el P.U. Promedio
    @property
    def precio_unitario_promedio(self):
        from django.db.models import Avg
        # Busca todas las recepciones de este material y saca el promedio del precio
        promedio = self.detallerecepcion_set.aggregate(Avg('precio_unitario'))['precio_unitario__avg']
        return round(promedio, 2) if promedio else 0.00
    
    # NUEVA FUNCIÓN: Calcula el valor total del inventario de este ítem
    @property
    def valor_total_inventario(self):
        # Convertimos ambos a "float" para evitar el choque de tipos de datos
        total = float(self.stock_actual) * float(self.precio_unitario_promedio)
        return round(total, 2)

    # 2. Función para saber los datos de la ÚLTIMA vez que llegó este material (Para el Modal)
    @property
    def ultima_recepcion(self):
        return self.detallerecepcion_set.order_by('-fecha_recepcion', '-id').first()

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
    
    # --- NUEVO CAMPO ---
    descripcion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Descripción General")
    
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
# ==========================================
# 3. TABLA HIJA: CONTROL DE ENTRADA (EM/EA/EDC)
# ==========================================
class DetalleRecepcion(models.Model):
    reporte = models.ForeignKey(ReporteRecepcion, on_delete=models.CASCADE, verbose_name="Reporte (RP)")
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Material")
    
    # OJO: Le quitamos el unique=True porque ahora varios materiales compartirán el mismo EM
    fecha_recepcion = models.DateField(default=timezone.now, verbose_name="Fecha de Recepción")
    nro_control_entrada = models.CharField(max_length=20, blank=True, verbose_name="Nro. Control (EM/EA)")
    
    nro_odc = models.CharField(max_length=50, verbose_name="Orden de Compra (ODC)")
    nro_nota_entrega = models.CharField(max_length=50, verbose_name="Nota de Entrega")
    proveedor = models.CharField(max_length=200, verbose_name="Proveedor")
    
    cantidad_solicitada = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cant. Solicitada (ODC)")
    cantidad_recibida = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cant. Recibida Física")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="U.P. (USD)")

    # Observaciones Manuales
    observaciones = models.CharField(max_length=255, blank=True, null=True, verbose_name="Observaciones")

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None
        
        if not self.nro_control_entrada:
            # 1. VERIFICAR SI LA ODC YA TIENE UN EM EN ESTE REPORTE
            item_existente = DetalleRecepcion.objects.filter(
                reporte=self.reporte, 
                nro_odc=self.nro_odc
            ).first()

            if item_existente and item_existente.nro_control_entrada:
                # Si ya existe, agrupamos bajo el mismo código
                self.nro_control_entrada = item_existente.nro_control_entrada
            else:
                # 2. SI ES UNA ODC NUEVA, GENERAMOS UN EM/EA/EDC NUEVO
                mapa_prefijos = {
                    'MATERIAL': 'EM',
                    'ACTIVOS': 'EA',
                    'DIRECTO AL GASTO': 'EDC'
                }
                prefijo = mapa_prefijos.get(self.material.tipo, 'EM') 
                
                año_corto = self.fecha_recepcion.strftime('%y') 
                inicio_codigo = f"{prefijo}{año_corto}" # Ej: 'EM26' o 'EA26'
                
                ultimo_detalle = DetalleRecepcion.objects.filter(
                    nro_control_entrada__startswith=inicio_codigo
                ).order_by('id').last()

                if ultimo_detalle:
                    try:
                        ultimo_num = int(ultimo_detalle.nro_control_entrada[-4:])
                        nuevo_num = ultimo_num + 1
                    except ValueError:
                        nuevo_num = 1
                else:
                    nuevo_num = 1
                    
                self.nro_control_entrada = f"{inicio_codigo}{nuevo_num:04d}"

        super().save(*args, **kwargs)
        
        # Sumar al inventario maestro
        if es_nuevo:
            self.material.stock_actual += self.cantidad_recibida
            self.material.save()

    def __str__(self):
        return f"{self.nro_control_entrada} - {self.material.codigo}"

    class Meta:
        verbose_name = "Recepción de Material"
        verbose_name_plural = "Control de Entradas"

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