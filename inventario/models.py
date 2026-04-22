from decimal import Decimal

from django.db import models, transaction
from django.db.models import Sum
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
    

    CARGO_CHOICES = [
        ('MANTENIMIENTO', 'Mantenimiento'),
        ('OPERACIONES', 'Operaciones'),
        ('TRANSPORTE', 'Transporte'),
        ('OTRO', 'Otro'),
    ]
    
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código Material")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción del Material")
    # Ampliamos el max_length a 20 para que quepa la palabra "DIRECTO AL GASTO"
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='MATERIAL', verbose_name="Tipo de Material")
    cargo = models.CharField(max_length=50, choices=CARGO_CHOICES, default='OPERACIONES', verbose_name="Cargo / Uso")
    nro_parte = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Parte")
    unidad_medida = models.CharField(max_length=20, verbose_name="U.M.")
    ubicacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ubicación")
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Stock Actual")

# ... (tus campos existentes de la clase Material) ...

    # 1. Función para calcular el P.U. Promedio (queda como referencia, NO se usa para FIFO)
    @property
    def precio_unitario_promedio(self):
        from django.db.models import Avg
        promedio = self.detallerecepcion_set.aggregate(Avg('precio_unitario'))['precio_unitario__avg']
        return round(promedio, 2) if promedio else Decimal('0.00')

    # 2. Función para obtener el lote FIFO activo
    @property
    def lote_fifo(self):
        for lote in self.detallerecepcion_set.order_by('fecha_recepcion', 'id'):
            if lote.cantidad_disponible > Decimal('0.00'):
                return lote
        return None

    @property
    def precio_unitario_fifo(self):
        lote = self.lote_fifo
        return lote.precio_unitario if lote else Decimal('0.00')

    @property
    def odc_fifo(self):
        lote = self.lote_fifo
        return lote.nro_odc if lote else None

    @property
    def valor_total_inventario(self):
        total = Decimal('0.00')
        for lote in self.detallerecepcion_set.order_by('fecha_recepcion', 'id'):
            total += lote.cantidad_disponible * (lote.precio_unitario or Decimal('0.00'))
        return total.quantize(Decimal('0.01'))

    @property
    def valor_total_inventario_fifo(self):
        return self.valor_total_inventario

    # 3. Función para saber los datos de la ÚLTIMA vez que llegó este material (Para el Modal)
    @property
    def ultima_recepcion(self):
        return self.detallerecepcion_set.order_by('-fecha_recepcion', '-id').first()

    @property
    def lote_actual(self):
        return self.lote_fifo or self.ultima_recepcion

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
    
    # --- NUEVOS CAMPOS ---
    descripcion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Descripción General")
    estado = models.CharField(
        max_length=10, 
        choices=[('ABIERTO', 'Abierto'), ('CERRADO', 'Cerrado')], 
        default='ABIERTO', 
        verbose_name="Estado"
    )
    
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
    reporte = models.ForeignKey(ReporteRecepcion, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Reporte (RP)")
    material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Material (Cód. Catálogo)")
    descripcion_entrada = models.CharField(max_length=500, blank=True, null=True, verbose_name="Descripción (según ODC)")
    
    # OJO: Le quitamos el unique=True porque ahora varios materiales compartirán el mismo EM
    fecha_recepcion = models.DateField(default=timezone.now, verbose_name="Fecha de Recepción")
    nro_rq = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nro. RQ")
    departamento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Dpto / Equipo")
    nro_control_entrada = models.CharField(max_length=20, blank=True, verbose_name="Nro. Control (EM/EA)")
    
    nro_odc = models.CharField(max_length=50, verbose_name="Orden de Compra (ODC)")
    nro_nota_entrega = models.CharField(max_length=50, verbose_name="Nota de Entrega")
    proveedor = models.CharField(max_length=200, verbose_name="Proveedor")
    
    cantidad_solicitada = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cant. Solicitada (ODC)")
    cantidad_recibida = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cant. Recibida Física")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="U.P. (USD)")
    moneda = models.CharField(max_length=10, default="USD", verbose_name="Moneda")
    eta = models.DateField(blank=True, null=True, verbose_name="ETA")
    fecha_firma_odc = models.DateField(blank=True, null=True, verbose_name="Fecha de Firma ODC")
    volumen_carpeta = models.CharField(max_length=50, blank=True, null=True, verbose_name="Volumen Carpeta")
    


    # Observaciones Manuales
    observaciones = models.CharField(max_length=255, blank=True, null=True, verbose_name="Observaciones")



    @property
    def cantidad_despachada(self):
        total = self.salidamaterialdetalle_set.aggregate(total=Sum('cantidad'))['total']
        return total or Decimal('0.00')

    @property
    def cantidad_disponible(self):
        disponible = self.cantidad_recibida - self.cantidad_despachada
        return disponible if disponible > Decimal('0.00') else Decimal('0.00')

    @property
    def valor_solicitado(self):
        if self.cantidad_solicitada and self.precio_unitario:
            return (self.cantidad_solicitada * self.precio_unitario).quantize(Decimal('0.01'))
        return Decimal('0.00')

    @property
    def valor_recibido(self):
        if self.cantidad_recibida and self.precio_unitario:
            return (self.cantidad_recibida * self.precio_unitario).quantize(Decimal('0.01'))
        return Decimal('0.00')

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None

        # --- NUEVA LÓGICA DE AUDITORÍA DE STOCK ---
        # Detectamos si el Jefe le acaba de asignar el material hoy (antes no tenía)
        se_asigno_material_ahora = False
        if not es_nuevo and self.material:
            registro_viejo = DetalleRecepcion.objects.get(pk=self.pk)
            if registro_viejo.material is None:
                se_asigno_material_ahora = True
        
        if not self.nro_control_entrada:
            # Si no hay material, usamos prefijo EM por defecto
            if self.material:
                mapa_prefijos = {
                    'MATERIAL': 'EM',
                    'ACTIVOS': 'EA',
                    'DIRECTO AL GASTO': 'EDG'
                }
                prefijo = mapa_prefijos.get(self.material.tipo, 'EM')
            else:
                prefijo = 'EM'
            
            año_corto = self.fecha_recepcion.strftime('%y') 
            inicio_codigo = f"{prefijo}{año_corto}"
            
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
        
        # --- SUMAR STOCK CORREGIDO ---
        # Sumamos 1) Si lo crearon de una vez con material OR 2) Si el Jefe lo acaba de clasificar
        if (es_nuevo and self.material) or se_asigno_material_ahora:
            self.material.stock_actual += self.cantidad_recibida
            self.material.save()

    def __str__(self):
        mat_str = self.material.codigo if self.material else (self.descripcion_entrada or "Sin descripción")
        return f"{self.nro_control_entrada} - {mat_str}"

    class Meta:
        verbose_name = "Entradas del Almacen"
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

    # --- CAMPOS FINANCIEROS Y DE PLANIFICACIÓN ---
    # Departamento: quién solicita el material (determina las partidas presupuestarias)
    departamento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Departamento Solicitante")
    # Centro de Costo: hacia dónde va dirigida la salida (campo informativo independiente)
    centro_costo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Centro de Costo")
    cuenta_contable = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cuenta Contable")
    partida_presupuestaria = models.CharField(max_length=100, blank=True, null=True, verbose_name="Partida Presupuestaria")


    @property
    def odc_origen(self):
        detalles = self.detalles.order_by('detalle_recepcion__fecha_recepcion', 'detalle_recepcion__id')
        if not detalles.exists():
            return None
        if detalles.count() > 1:
            return "Múltiples ODCs"
        return detalles.first().detalle_recepcion.nro_odc

    @property
    def precio_unitario_origen(self):
        first_detail = self.detalles.order_by('detalle_recepcion__fecha_recepcion', 'detalle_recepcion__id').first()
        return first_detail.precio_unitario if first_detail else Decimal('0.00')

    def clean(self):
        if self.pk is None:
            disponible_total = sum(
                lote.cantidad_disponible for lote in self.material.detallerecepcion_set.order_by('fecha_recepcion', 'id')
            )
            if self.cantidad > disponible_total:
                raise ValidationError({'cantidad': f"Falta stock FIFO. Solo quedan: {disponible_total}"})

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None

        # --- LÓGICA FINANCIERA ---
        # El DEPARTAMENTO (quién solicita) es el que determina la partida presupuestaria.
        # El CENTRO DE COSTO es solo hacia dónde va la salida (informativo, no busca en presupuesto).
        if self.departamento and not self.cuenta_contable:
            año_actual = self.fecha_despacho.year

            # Busca en el maestro de finanzas usando el departamento solicitante
            presupuesto = PresupuestoAnual.objects.filter(
                anio=año_actual,
                departamento__iexact=self.departamento
            ).first()

            # Si encuentra la regla, inyecta cuenta y partida automáticamente
            if presupuesto:
                self.cuenta_contable = presupuesto.cuenta_contable
                self.partida_presupuestaria = presupuesto.partida

        with transaction.atomic():
            super().save(*args, **kwargs)

            if es_nuevo:
                remaining = self.cantidad
                for lote in self.material.detallerecepcion_set.order_by('fecha_recepcion', 'id'):
                    if remaining <= Decimal('0.00'):
                        break
                    disponible = lote.cantidad_disponible
                    if disponible <= Decimal('0.00'):
                        continue

                    cantidad_a_despachar = min(disponible, remaining)
                    SalidaMaterialDetalle.objects.create(
                        salida=self,
                        detalle_recepcion=lote,
                        cantidad=cantidad_a_despachar,
                        precio_unitario=lote.precio_unitario or Decimal('0.00'),
                        subtotal=cantidad_a_despachar * (lote.precio_unitario or Decimal('0.00'))
                    )
                    remaining -= cantidad_a_despachar

                if remaining > Decimal('0.00'):
                    raise ValidationError({'cantidad': 'No hay ODC suficiente para esta salida.'})

                self.material.stock_actual -= self.cantidad
                self.material.save()

    def __str__(self):
        return f"RIM: {self.nro_rim} - {self.material.codigo}"

    class Meta:
        verbose_name = "Despacho RIM"
        verbose_name_plural = "3. Relación de Despachos (RIM)"


class SalidaMaterialDetalle(models.Model):
    salida = models.ForeignKey(SalidaMaterial, on_delete=models.CASCADE, related_name='detalles', verbose_name="Salida")
    detalle_recepcion = models.ForeignKey(DetalleRecepcion, on_delete=models.PROTECT, verbose_name="ODC Origen")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad desde ODC")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio Unitario ODC")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Subtotal")

    def __str__(self):
        return f"{self.salida.nro_rim} - {self.detalle_recepcion.nro_odc} ({self.cantidad})"

    class Meta:
        verbose_name = "Detalle de Salida FIFO"
        verbose_name_plural = "Detalles de Salida FIFO"

# ==========================================
# TABLA FINANCIERA (Diccionario de Partidas)
# ==========================================
class PresupuestoAnual(models.Model):
    anio = models.IntegerField(verbose_name="Año Fiscal (Ej. 2026)")
    departamento = models.CharField(max_length=100, verbose_name="Dpto / Centro de Costo")
    
    # Los datos secretos de finanzas
    cuenta_contable = models.CharField(max_length=100, verbose_name="Cuenta Contable")
    descripcion_cuenta = models.CharField(max_length=200, blank=True, null=True, verbose_name="Descripción Cuenta")
    partida = models.CharField(max_length=200, verbose_name="Partida Presupuestaria")

    def __str__(self):
        return f"{self.departamento} | Cta: {self.cuenta_contable} | {self.partida}"

    class Meta:
        verbose_name = "Partida Presupuestaria"
        verbose_name_plural = "Config. Finanzas (Partidas)"


# ==========================================
# TABLA: CENTROS DE COSTO
# ==========================================
class CentroCosto(models.Model):
    nombre = models.CharField(max_length=150, unique=True, verbose_name="Centro de Costo")
    descripcion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Descripción")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Centro de Costo"
        verbose_name_plural = "Config. Centros de Costo"
        ordering = ['nombre']