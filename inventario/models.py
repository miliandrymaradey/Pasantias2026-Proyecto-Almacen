from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum, Max
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
import datetime

def hora_local_actual():
    return timezone.localtime(timezone.now()).time()


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
    codigo_qr = models.ImageField(upload_to='qrcodes/', blank=True, null=True, verbose_name="Código QR")

    # Auditoría temporal (Pilar 5)
    creado_en = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, null=True, verbose_name="Última Modificación")

# ... (tus campos existentes de la clase Material) ...

    # 1. Función para calcular el P.U. Promedio (queda como referencia, NO se usa para FIFO)
    @property
    def precio_unitario_promedio(self):
        from django.db.models import Avg
        promedio = self.entradas.aggregate(Avg('precio_unitario'))['precio_unitario__avg']
        return round(promedio, 2) if promedio else Decimal('0.00')

    # 2. Función para obtener el lote FIFO activo
    @property
    def lote_fifo(self):
        """Devuelve el primer objeto DetalleRecepcion con stock disponible (FIFO)."""
        # Usamos .all() para aprovechar el prefetch_related si existe en la consulta
        lotes = self.entradas.all()
        # Si no hay prefetch con orden, forzamos el orden FIFO en memoria o BD
        if not lotes._result_cache:
            lotes = lotes.order_by('fecha_recepcion', 'id')
        
        for lote in lotes:
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
        for lote in self.entradas.order_by('fecha_recepcion', 'id'):
            total += lote.cantidad_disponible * (lote.precio_unitario or Decimal('0.00'))
        return total.quantize(Decimal('0.01'))

    @property
    def valor_total_inventario_fifo(self):
        return self.valor_total_inventario

    # 3. Función para saber los datos de la ÚLTIMA vez que llegó este material (Para el Modal)
    @property
    def ultima_recepcion(self):
        return self.entradas.order_by('-fecha_recepcion', '-id').first()

    @property
    def lote_actual(self):
        """
        Retorna el objeto DetalleRecepcion completo del lote activo.
        Prioriza el lote FIFO con stock, si no hay, devuelve la última recepción.
        """
        return self.lote_fifo or self.ultima_recepcion

    def __str__(self):
        return f"[{self.tipo}] {self.codigo} - {self.descripcion}"

    def save(self, *args, **kwargs):
        # Generar código QR si no existe y tiene un código asignado
        if not self.codigo_qr and self.codigo:
            import qrcode
            from io import BytesIO
            from django.core.files import File
            
            qr_content = f"[{self.tipo}] | Código: {self.codigo} | Desc: {self.descripcion}"
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_content)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            self.codigo_qr.save(f"qr_{self.codigo}.png", File(buffer), save=False)
            
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "1. Registro Maestro"
        ordering = ['codigo']


# ==========================================
# 1B. REGISTRO DE ACTIVOS FIJOS
# ==========================================
class Activo(models.Model):
    """
    Modelo para el control de inventario físico de Activos Fijos (Herramientas, Equipos, etc.)
    Separado de Materiales para evitar mezclar lógica financiera con inventario físico puro.
    """
    codigo_activo = models.CharField(max_length=50, unique=True, verbose_name="Código de Activo")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción del Activo")
    marca = models.CharField(max_length=100, blank=True, null=True, verbose_name="Marca")
    modelo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Modelo")
    serial = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nro. de Serie")
    stock = models.IntegerField(default=0, verbose_name="Stock Cantidad")
    ubicacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ubicación Física")

    # Campos adicionales agregados en Supabase
    unidad_medida_ac = models.CharField(max_length=50, default='UNID', verbose_name="Unidad de Medida")
    nro_parte_ac = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nro. de Parte")
    cargo_ac = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cargo / Departamento")
    codigo_qr = models.ImageField(upload_to='qrcodes/', blank=True, null=True, verbose_name="Código QR")

    # Auditoría
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha Registro")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    @property
    def stock_final(self):
        from django.db.models import Sum
        
        # 1. Sumar todas las entradas vinculadas a este activo
        entradas_agg = self.entradas.aggregate(total=Sum('cantidad_recibida'))
        total_entradas = entradas_agg['total'] or 0
        
        # 2. Sumar todas las salidas vinculadas a este activo
        salidas_agg = self.salidas.aggregate(total=Sum('cantidad'))
        total_salidas = salidas_agg['total'] or 0
        
        # 3. Retornar el cálculo exacto
        return int(total_entradas) - int(total_salidas)

    def __str__(self):
        return f"{self.codigo_activo} - {self.descripcion}"

    def save(self, *args, **kwargs):
        # Generar código QR si no existe y tiene un código asignado
        if not self.codigo_qr and self.codigo_activo:
            import qrcode
            from io import BytesIO
            from django.core.files import File
            
            qr_content = f"[ACTIVO] | Código: {self.codigo_activo} | Desc: {self.descripcion}"
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_content)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            self.codigo_qr.save(f"qr_{self.codigo_activo}.png", File(buffer), save=False)
            
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'inventario_activo'
        verbose_name = "Activo Fijo"
        verbose_name_plural = "1B. Inventario de Activos Fijos"
        ordering = ['codigo_activo']


# ==========================================
# 2. TABLA PADRE: REPORTE DE RECEPCIÓN (RP)
# ==========================================
class ReporteRecepcion(models.Model):
    nro_reporte = models.CharField(max_length=20, unique=True, blank=True, verbose_name="No. Reporte (RP)")
    fecha_recepcion = models.DateField(default=datetime.date.today, db_index=True, verbose_name="Fecha de Recepción")
    
    # --- NUEVOS CAMPOS ---
    descripcion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Descripción General")
    estado = models.CharField(
        max_length=10, 
        choices=[('ABIERTO', 'Abierto'), ('CERRADO', 'Cerrado')], 
        default='ABIERTO', 
        db_index=True,
        verbose_name="Estado"
    )

    # Auditoría temporal (Pilar 5)
    creado_en = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, null=True, verbose_name="Última Modificación")
    
    def save(self, *args, **kwargs):
        # Lógica de Autogeneración Correlativa: RP-XXX-YY
        if not self.nro_reporte:
            # Usamos transaction.atomic para asegurar la integridad de la secuencia
            with transaction.atomic():
                año_actual = self.fecha_recepcion.year
                año_corto = self.fecha_recepcion.strftime('%y')
                
                # Buscamos el último reporte del año actual usando select_for_update para evitar duplicados
                ultimo_reporte = ReporteRecepcion.objects.filter(
                    fecha_recepcion__year=año_actual
                ).select_for_update().order_by('-nro_reporte').first()

                if ultimo_reporte:
                    try:
                        # Extraemos el número correlativo (asumiendo formato RP-XXX-YY)
                        partes = ultimo_reporte.nro_reporte.split('-')
                        if len(partes) >= 2:
                            ultimo_numero = int(partes[1])
                            nuevo_numero = ultimo_numero + 1
                        else:
                            nuevo_numero = 1
                    except (ValueError, IndexError):
                        nuevo_numero = 1
                else:
                    # --- REGLAS DE INICIO (SI NO HAY REPORTES EN EL AÑO) ---
                    if año_actual == 2026:
                        # Regla Especial 2026: Iniciar en 16 para empatar con la papelería física
                        nuevo_numero = 16
                    else:
                        # Reinicio estándar para años futuros: Iniciar en 1
                        nuevo_numero = 1

                # Formateamos el código final: Ej. RP-016-26 o RP-001-27
                self.nro_reporte = f"RP-{nuevo_numero:03d}-{año_corto}"
                
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nro_reporte} ({self.fecha_recepcion.strftime('%d/%m/%Y')})"

    class Meta:
        verbose_name = "Reporte de Recepción"
        verbose_name_plural = "2. Reportes Diarios (RP)"
        ordering = ['-fecha_recepcion', '-id']


# ==========================================
# 3. TABLA HIJA: CONTROL DE ENTRADA (EM/EA/EDC)
# ==========================================

# ==========================================
# 1C. REGISTRO DE GASTO DIRECTO (EDG)
# ==========================================
class GastoDirecto(models.Model):
    """
    Modelo para el catálogo de artículos 'Directo al Gasto' (EDG).
    Conectado a la tabla manual 'inventario_DG' en Supabase.
    """
    codigo_dg = models.CharField(max_length=50, unique=True, verbose_name="Código DG")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")
    unidad_medida_dg = models.CharField(max_length=20, verbose_name="U.M.")
    nro_parte_dg = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nro. Parte")
    cargo_dg = models.CharField(max_length=50, verbose_name="Cargo")
    stock = models.IntegerField(default=0, verbose_name="Stock")

    class Meta:
        db_table = 'inventario_DG'
        managed = False # La tabla ya existe en Supabase
        verbose_name = "Artículo Directo al Gasto"
        verbose_name_plural = "1C. Catálogo de Gasto Directo (EDG)"

    def __str__(self):
        return f"{self.codigo_dg} - {self.descripcion}"


class DetalleRecepcion(models.Model):
    TIPO_INGRESO_CHOICES = [
        ('Material', 'Material'),
        ('Activo', 'Activo'),
    ]
    reporte = models.ForeignKey(ReporteRecepcion, on_delete=models.SET_NULL, null=True, blank=True, related_name='entradas', verbose_name="Reporte (RP)")
    tipo_ingreso = models.CharField(max_length=30, choices=TIPO_INGRESO_CHOICES, default='Material', verbose_name="Tipo de Ingreso")
    material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True, blank=True, related_name='entradas', verbose_name="Material (Cód. Catálogo)")
    gasto_directo = models.ForeignKey(GastoDirecto, on_delete=models.SET_NULL, null=True, blank=True, related_name='entradas', verbose_name='Gasto Directo (Cód. DG)')
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE, null=True, blank=True, related_name='entradas', verbose_name="Activo (Cód. Catálogo)")
    descripcion_entrada = models.CharField(max_length=500, blank=True, null=True, verbose_name="Descripción (según ODC)")
    
    # OJO: Le quitamos el unique=True porque ahora varios materiales compartirán el mismo EM
    fecha_recepcion = models.DateField(default=datetime.date.today, db_index=True, verbose_name="Fecha de Recepción")
    nro_rq = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nro. RQ")
    departamento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Dpto / Equipo")
    nro_control_entrada = models.CharField(max_length=20, blank=True, db_index=True, verbose_name="Nro. Control (EM/EA)")
    
    nro_odc = models.CharField(max_length=50, db_index=True, verbose_name="Orden de Compra (ODC)")
    nro_nota_entrega = models.CharField(max_length=50, verbose_name="Nota de Entrega")
    proveedor = models.CharField(max_length=200, verbose_name="Proveedor")
    
    cantidad_solicitada = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cant. Solicitada (ODC)")
    cantidad_recibida = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cant. Recibida Física")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="U.P. (USD)")
    
    MONEDA_CHOICES = [('USD', 'USD'), ('BS', 'Bolívares'), ('EUR', 'EUR')]
    moneda = models.CharField(max_length=10, default="USD", choices=MONEDA_CHOICES, verbose_name="Moneda")
    
    eta = models.DateField(blank=True, null=True, verbose_name="ETA")
    fecha_firma_odc = models.DateField(blank=True, null=True, verbose_name="Fecha de Firma ODC")
    volumen_carpeta = models.CharField(max_length=50, blank=True, null=True, verbose_name="Volumen Carpeta")
    


    # Observaciones Manuales
    es_saldo_inicial = models.BooleanField(default=False, verbose_name="¿Es Saldo Inicial?")
    observaciones = models.CharField(max_length=255, blank=True, null=True, verbose_name="Observaciones")

    # ── AUDITORÍA DE USUARIO (Pilar 1) ───────────────────────────────────────
    # Registra qué almacenista registró esta entrada. SET_NULL preserva el
    # historial si el usuario es eliminado del sistema.
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entradas_creadas',
        verbose_name="Registrado por"
    )

    # Auditoría temporal (Pilar 5)
    creado_en = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, null=True, verbose_name="Última Modificación")


    @property
    def cantidad_despachada(self):
        """Calcula el total despachado. Optimizado para usar prefetch si está disponible."""
        # Si la relación ya fue precargada (prefetch_related), sumamos en memoria para evitar queries N+1
        if hasattr(self, '_prefetched_objects_cache') and 'detalles_salida' in self._prefetched_objects_cache:
            return sum((d.cantidad for d in self.detalles_salida.all()), Decimal('0.00'))
            
        total = self.detalles_salida.aggregate(total=Sum('cantidad'))['total']
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

        # --- LÓGICA DE ACTUALIZACIÓN DE STOCK (MATERIAL Y ACTIVO) ---
        # Si es un nuevo registro y tiene material asociado
        if es_nuevo and self.material:
            # Validamos que sea ingreso de tipo Material (insensible a mayúsculas)
            if str(self.tipo_ingreso).lower() == 'material':
                self.material.stock_actual += self.cantidad_recibida
                self.material.save()

        # Si es un nuevo registro y tiene activo asociado
        if es_nuevo and self.activo:
            # Validamos que sea ingreso de tipo Activo (insensible a mayúsculas)
            if str(self.tipo_ingreso).lower() == 'activo':
                self.activo.stock += int(self.cantidad_recibida)
                self.activo.save()


        # --- LÓGICA DE CORRELATIVO PERSONALIZADO (EM/EA/EDG) ---
        if not self.nro_control_entrada:
            from django.db import transaction
            with transaction.atomic():
                mapa_prefijos = {
                    'MATERIAL': 'EM',
                    'ACTIVOS': 'EA',
                    'DIRECTO AL GASTO': 'EDG'
                }
                tipo_manual = getattr(self, '_tipo_entrada_manual', None)

                if tipo_manual and tipo_manual in mapa_prefijos:
                    prefijo = mapa_prefijos[tipo_manual]
                elif self.tipo_ingreso == 'Activo':
                    prefijo = 'EA'
                elif self.material:
                    prefijo = mapa_prefijos.get(self.material.tipo, 'EM')
                else:
                    prefijo = 'EM'
                
                año_actual = self.fecha_recepcion.year
                año_corto = self.fecha_recepcion.strftime('%y')
                inicio_codigo = f"{prefijo}{año_corto}" 
                
                ultimo_detalle = DetalleRecepcion.objects.filter(
                    nro_control_entrada__startswith=inicio_codigo
                ).select_for_update().order_by('-nro_control_entrada').first()

                if ultimo_detalle:
                    try:
                        nuevo_num = int(ultimo_detalle.nro_control_entrada[-4:]) + 1
                    except (ValueError, IndexError):
                        nuevo_num = 1
                else:
                    nuevo_num = 38 if año_actual == 2026 else 1
                    
                self.nro_control_entrada = f"{inicio_codigo}{nuevo_num:04d}"

        super().save(*args, **kwargs)

    def __str__(self):
        if self.tipo_ingreso == 'Material' and self.material:
            mat_str = self.material.codigo
        elif self.tipo_ingreso == 'Activo' and self.activo:
            mat_str = self.activo.codigo_activo
        else:
            mat_str = self.descripcion_entrada or "Sin descripción"
        return f"{self.nro_control_entrada} - {mat_str}"

    class Meta:
        verbose_name = "Entradas del Almacen"
        verbose_name_plural = "Control de Entradas"
        ordering = ['-fecha_recepcion', '-id']

# ==========================================
# 4. TABLA: GUÍA DE TRASLADO (Documento de Transporte)- salidas
# ==========================================
class GuiaTraslado(models.Model):
    TALADROS = [
        ('PRV-1', 'PRV-1'),
        ('PRV-2', 'PRV-2'),
        ('PRV-3', 'PRV-3'),
        ('PRV-4', 'PRV-4'),
        ('PRV-5', 'PRV-5'),
        ('PRV-6', 'PRV-6'),
        ('PRV-7', 'PRV-7'),
        ('TERCEROS', 'ALM'),
    ]

    # Datos de la Guía
    nro_guia = models.CharField(max_length=50, unique=True, blank=True, verbose_name="No. Guía (Automático)")
    fecha = models.DateField(default=datetime.date.today, db_index=True, verbose_name="Fecha")
    hora = models.TimeField(default=hora_local_actual, verbose_name="Hora")
    taladro_destino = models.CharField(max_length=20, choices=TALADROS, db_index=True, verbose_name="Destino")
    
    # Destino Físico
    direccion = models.CharField(max_length=255, verbose_name="Dirección")
    ciudad = models.CharField(max_length=100, default="MORICHAL", verbose_name="Ciudad")

    # Datos del Transportista (Camión)
    conductor = models.CharField(max_length=100, verbose_name="Conductor")
    ci_conductor = models.CharField(max_length=20, verbose_name="C.I.")
    vehiculo = models.CharField(max_length=50, verbose_name="Vehículo (Ej. CARGO)")
    color = models.CharField(max_length=30, verbose_name="Color")
    placa = models.CharField(max_length=20, verbose_name="Placa")
    marca = models.CharField(max_length=100, null=True, blank=True, verbose_name="Marca")
    modelo = models.CharField(max_length=100, null=True, blank=True, verbose_name="Modelo")

    # Observaciones y Firmas
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    nombre_entregado = models.CharField(max_length=100, default="Almacén El Tigre", verbose_name="Entregado por")
    nombre_aprobador = models.CharField(max_length=100, null=True, blank=True, verbose_name="Aprobado en Almacén por")

    # ── AUDITORÍA DE USUARIO (Pilar 1) ───────────────────────────────────────
    # Registra qué almacenista generó la guía. SET_NULL preserva la guía
    # si el usuario es eliminado del sistema.
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guias_creadas',
        verbose_name="Generado por"
    )

    # Auditoría temporal (Pilar 5)
    creado_en = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, null=True, verbose_name="Última Modificación")

    @property
    def conductor_abreviado(self):
        """Retorna primer nombre y primer apellido (ej: Juan Carlos Pérez -> Juan Pérez)"""
        if not self.conductor:
            return ""
        palabras = self.conductor.strip().split()
        if len(palabras) >= 3:
            # Caso: Juan Carlos Perez... -> Juan Perez
            return f"{palabras[0]} {palabras[2]}"
        elif len(palabras) == 2:
            # Caso: Juan Perez -> Juan Perez
            return f"{palabras[0]} {palabras[1]}"
        return palabras[0]

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
        ordering = ['-fecha', '-id']


# ==========================================
# 5. TABLA: SALIDA DE MATERIAL (El Despacho Real)
# ==========================================
class SalidaMaterial(models.Model):
    # LA FUSIÓN: Este campo conecta la Salida con la Guía. Es OPCIONAL (null=True, blank=True)
    guia = models.ForeignKey(GuiaTraslado, on_delete=models.SET_NULL, null=True, blank=True, related_name='salidas', verbose_name="¿Va en alguna Guía?")
    
    # Datos de la salida
    TIPO_SALIDA_CHOICES = [
        ('SM', 'Salida de Materiales'),
        ('SA', 'Salida de Activos'),
        ('SDG', 'Salida Directo al Gasto'),
    ]
    tipo_salida = models.CharField(max_length=5, choices=TIPO_SALIDA_CHOICES, default='SM', verbose_name="Tipo de Salida")
    numero_salida_correlativo = models.CharField(max_length=4, blank=True, null=True, verbose_name="Nro. Correlativo")

    # ⚠️ PROTECT (no CASCADE): evita borrar el historial de despachos si se
    # elimina el material del maestro. Django rechazará el borrado del Material
    # si este tiene salidas registradas, protegiendo la trazabilidad.
    # Enlace al Maestro (Polimorfismo manual)
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='salidas', null=True, blank=True, verbose_name="Material a Despachar")
    gasto_directo = models.ForeignKey(GastoDirecto, on_delete=models.SET_NULL, null=True, blank=True, related_name='despachos', verbose_name='Gasto Directo (Cód. DG)')
    activo = models.ForeignKey(Activo, on_delete=models.PROTECT, related_name='salidas', null=True, blank=True, verbose_name="Activo a Despachar")
    
    fecha_despacho = models.DateField(default=datetime.date.today, db_index=True, verbose_name="Fecha de Despacho")
    nro_rim = models.CharField(
        max_length=50, 
        db_index=True,
        verbose_name="No. RIM (Requisición)",
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{3,4}-\d{3}-\d{4}$',
                message='El formato del Nro. RIM es inválido. Debe seguir el patrón DPT-000-AÑO (Ej. OPE-001-2026).',
                code='invalid_rim_format'
            )
        ]
    )
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad Despachada")

    @property
    def codigo_salida_completo(self):
        """Retorna el código de salida compuesto (Ej: SM-0015)"""
        if self.tipo_salida and self.numero_salida_correlativo:
            return f"{self.tipo_salida}-{self.numero_salida_correlativo}"
        return self.nro_rim # Fallback


    # --- CAMPOS FINANCIEROS Y DE PLANIFICACIÓN ---
    # Departamento: quién solicita el material (determina las partidas presupuestarias)
    departamento = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name="Departamento Solicitante")
    # Centro de Costo: hacia dónde va dirigida la salida (campo informativo independiente)
    centro_costo_texto = models.CharField(max_length=100, blank=True, null=True, verbose_name="Centro de Costo (Texto)")
    centro_costo = models.ForeignKey('CentroCosto', on_delete=models.SET_NULL, null=True, blank=True, related_name='salidas', verbose_name="Centro de Costo")
    
    nro_sm = models.CharField(max_length=50, blank=True, null=True, verbose_name="No. SM (Solicitud)")
    cuenta_contable = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cuenta Contable")
    descripcion_cuenta = models.CharField(max_length=200, blank=True, null=True, verbose_name="Descripción de la Cuenta")
    partida_presupuestaria = models.CharField(max_length=100, blank=True, null=True, verbose_name="Partida Presupuestaria")
    rubro_1 = models.CharField(max_length=100, blank=True, null=True, verbose_name="Rubro 1")
    rubro_2 = models.CharField(max_length=100, blank=True, null=True, verbose_name="Rubro 2")

    # ── AUDITORÍA DE USUARIO (Pilar 1) ───────────────────────────────────────
    # Registra qué almacenista ejecutó el despacho. SET_NULL preserva el
    # RIM si el usuario es eliminado del sistema.
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='despachos_creados',
        verbose_name="Despachado por"
    )

    # Auditoría temporal (Pilar 5)
    creado_en = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, null=True, verbose_name="Última Modificación")


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
            # Determinar qué objeto estamos despachando
            obj_origen = self.material if self.tipo_salida != 'SA' else self.activo
            
            if not obj_origen:
                raise ValidationError("Debe seleccionar un artículo para despachar.")

            disponible_total = sum(
                lote.cantidad_disponible for lote in obj_origen.entradas.order_by('fecha_recepcion', 'id')
            )
            if self.cantidad > disponible_total:
                raise ValidationError({'cantidad': f"Falta stock FIFO. Solo quedan: {disponible_total}"})

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None

        # --- LÓGICA DE CORRELATIVO AUTOMÁTICO (SM-0001) ---
        if not self.numero_salida_correlativo:
            with transaction.atomic():
                # 1. Determinar el prefijo (por defecto SM)
                prefijo = self.tipo_salida or 'SM'
                año_actual = self.fecha_despacho.year
                
                # 2. Buscar el último del mismo tipo y año
                ultimo_registro = SalidaMaterial.objects.filter(
                    tipo_salida=prefijo,
                    fecha_despacho__year=año_actual
                ).select_for_update().order_by('-numero_salida_correlativo').first()

                if ultimo_registro and ultimo_registro.numero_salida_correlativo:
                    try:
                        nuevo_num = int(ultimo_registro.numero_salida_correlativo) + 1
                    except ValueError:
                        nuevo_num = 1
                else:
                    # Regla de inicio (opcional: podrías empezar en un número específico si es 2026)
                    nuevo_num = 1
                
                # 3. Formatear a 4 dígitos
                self.numero_salida_correlativo = f"{nuevo_num:04d}"

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

            # Si encuentra la regla, inyecta cuenta, partida y rubros automáticamente
            if presupuesto:
                self.cuenta_contable = presupuesto.cuenta_contable
                self.descripcion_cuenta = presupuesto.descripcion_cuenta
                self.partida_presupuestaria = presupuesto.partida
                self.rubro_1 = presupuesto.rubro_1
                self.rubro_2 = presupuesto.rubro_2

        with transaction.atomic():
            super().save(*args, **kwargs)

            if es_nuevo:
                remaining = self.cantidad
                # Determinar qué objeto estamos despachando
                obj_origen = self.material if self.tipo_salida != 'SA' else self.activo
                
                if not obj_origen:
                    return # No hay nada que descontar

                for lote in obj_origen.entradas.order_by('fecha_recepcion', 'id'):
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
                    raise ValidationError({'cantidad': 'No hay stock FIFO suficiente para esta salida.'})

                if self.material:
                    self.material.stock_actual -= self.cantidad
                    self.material.save()
                elif self.activo:
                    self.activo.stock -= int(self.cantidad)
                    self.activo.save()

    def __str__(self):
        codigo = self.material.codigo if self.material else self.activo.codigo_activo if self.activo else "S/N"
        return f"RIM: {self.nro_rim} - {codigo}"

    class Meta:
        verbose_name = "Despacho RIM"
        verbose_name_plural = "3. Relación de Despachos (RIM)"
        ordering = ['-fecha_despacho', '-id']


class SalidaMaterialDetalle(models.Model):
    salida = models.ForeignKey(SalidaMaterial, on_delete=models.CASCADE, related_name='detalles', verbose_name="Salida")
    detalle_recepcion = models.ForeignKey(DetalleRecepcion, on_delete=models.PROTECT, related_name='detalles_salida', verbose_name="ODC Origen")
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad desde ODC")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio Unitario ODC")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Subtotal")

    # Auditoría temporal (Pilar 5)
    creado_en = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Fecha de Creación")
    actualizado_en = models.DateTimeField(auto_now=True, null=True, verbose_name="Última Modificación")

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
    rubro_1 = models.CharField(max_length=100, blank=True, null=True, verbose_name="Rubro 1")
    rubro_2 = models.CharField(max_length=100, blank=True, null=True, verbose_name="Rubro 2")

    def __str__(self):
        return f"{self.departamento} | Cta: {self.cuenta_contable} | {self.partida}"

    class Meta:
        verbose_name = "Partida Presupuestaria"
        verbose_name_plural = "Config. Finanzas (Partidas)"
        indexes = [
            models.Index(fields=['anio', 'departamento'], name='idx_presupuesto_anio_depto'),
        ]


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





# ==========================================
# PERFIL DE USUARIO (Foto e información extendida)
# ==========================================
class PerfilUsuario(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil', verbose_name="Usuario")
    debe_cambiar_clave = models.BooleanField(default=True, verbose_name="Debe cambiar contraseña")
    foto = models.ImageField(upload_to='perfiles/', null=True, blank=True, verbose_name="Foto de Perfil")

    def __str__(self):
        return f"Perfil de {self.user.username} - Cambio obligatorio: {self.debe_cambiar_clave}"

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"


# Receptor de Señal para Crear Perfil Automáticamente
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        PerfilUsuario.objects.get_or_create(user=instance)


# ==========================================
# REGISTRO DE ACTIVIDAD (AUDIT LOG)
# ==========================================
class RegistroActividad(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='actividades', verbose_name="Usuario")
    accion = models.CharField(max_length=100, verbose_name="Acción Realizada")
    detalles = models.TextField(blank=True, null=True, verbose_name="Detalles de la Acción")
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")

    def __str__(self):
        return f"{self.usuario.username} - {self.accion} - {self.fecha.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        verbose_name = "Registro de Actividad"
        verbose_name_plural = "Registros de Actividades"
        ordering = ['-fecha']


# --- SEÑALES PARA INVALIDACIÓN REACTIVA DE CACHÉ DE KPIs ---
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

@receiver([post_save, post_delete], sender=DetalleRecepcion)
@receiver([post_save, post_delete], sender=SalidaMaterialDetalle)
def invalidar_cache_kpis(sender, **kwargs):
    """
    Invalida de forma reactiva la caché de valorización del inventario en el Dashboard
    cada vez que se registre, modifique o elimine una entrada (lote) o salida (despacho).
    """
    cache.delete('kpis_valorizacion')