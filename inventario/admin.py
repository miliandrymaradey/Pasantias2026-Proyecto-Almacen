from django.contrib import admin
from .models import Material, ReporteRecepcion, DetalleRecepcion, SalidaMaterial
from .models import GuiaTraslado
# --- Configuración del Maestro ---
class MaterialAdmin(admin.ModelAdmin):
    # Agregamos 'tipo' a la lista para ver si es EM o EA
    list_display = ('codigo', 'tipo', 'descripcion', 'unidad_medida', 'stock_actual')
    search_fields = ('codigo', 'descripcion')
    list_filter = ('tipo',) # Agregamos un filtro lateral muy útil

# --- El Súper Formulario de Recepción ---
class DetalleRecepcionInline(admin.TabularInline):
    model = DetalleRecepcion
    extra = 1 
    # Bloqueamos estos campos para que nadie los pueda escribir a mano (Son automáticos)
    readonly_fields = ('nro_control_entrada', 'observaciones')

class ReporteRecepcionAdmin(admin.ModelAdmin):
    list_display = ('nro_reporte', 'fecha_recepcion')
    inlines = [DetalleRecepcionInline] 

# --- Vista del Control de Entradas ---
class DetalleRecepcionAdmin(admin.ModelAdmin):
    # ¡AQUÍ ESTÁ LA CORRECCIÓN! 
    # Agregamos 'nro_control_entrada' al inicio y cambiamos al nuevo nombre 'observaciones' al final
    list_display = ('nro_control_entrada', 'get_reporte', 'get_fecha', 'nro_odc', 'material', 'cantidad_solicitada', 'cantidad_recibida', 'observaciones')
    list_filter = ('reporte__fecha_recepcion', 'proveedor')
    search_fields = ('nro_control_entrada', 'nro_odc', 'nro_nota_entrega', 'material__descripcion')

    def get_reporte(self, obj):
        return obj.reporte.nro_reporte
    get_reporte.short_description = 'Reporte (RP)'

    def get_fecha(self, obj):
        return obj.reporte.fecha_recepcion
    get_fecha.short_description = 'Fecha'

# --- Configuración de Salidas ---
# 1. Vista de las Salidas Individuales
class SalidaAdmin(admin.ModelAdmin):
    list_display = ('fecha_despacho', 'nro_rim', 'material', 'cantidad', 'guia')
    search_fields = ('nro_rim', 'material__codigo')
    list_filter = ('fecha_despacho',)

# 2. Vista de las Guías (Con los items adentro)
class SalidaMaterialInline(admin.TabularInline):
    model = SalidaMaterial
    extra = 1
    # Campos que se muestran dentro de la guía
    fields = ['nro_rim', 'material', 'cantidad'] 

class GuiaTrasladoAdmin(admin.ModelAdmin):
    list_display = ('nro_guia', 'fecha', 'taladro_destino', 'conductor', 'placa')
    search_fields = ('nro_guia', 'taladro_destino')
    readonly_fields = ('nro_guia',) # El código automático no se edita a mano
    inlines = [SalidaMaterialInline] # Esto mete las salidas dentro de la guía

# Registrar en el panel
admin.site.register(GuiaTraslado, GuiaTrasladoAdmin)
admin.site.register(Material, MaterialAdmin)
admin.site.register(ReporteRecepcion, ReporteRecepcionAdmin)
admin.site.register(DetalleRecepcion, DetalleRecepcionAdmin)
admin.site.register(SalidaMaterial, SalidaAdmin)

# Register your models here.
