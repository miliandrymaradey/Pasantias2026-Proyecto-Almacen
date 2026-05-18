"""
URL configuration for sistema_wms project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views
from inventario import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),

    # --- RUTAS DE SEGURIDAD (LOGIN/LOGOUT) --- <- NUEVO
    path('login/', auth_views.LoginView.as_view(template_name='inventario/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', views.dashboard, name='dashboard'), # La página principal ahora es el Dashboard
    path('maestro/', views.lista_materiales, name='lista_materiales'),
    path('maestro/nuevo/', views.crear_material, name='crear_material'),
    path('entradas/', views.lista_entradas, name='lista_entradas'),

    
    # NUEVA RUTA DE REPORTES
    path('reportes/', views.reportes, name='reportes'),
    path('reportes/pendientes/', views.reportes_pendientes, name='reportes_pendientes'),
    path('reportes/desglosar/<int:detalle_id>/', views.desglosar_entrada, name='desglosar_entrada'),
    path('reportes/cambiar-estado/', views.cambiar_estado_reportes, name='cambiar_estado_reportes'),
    path('reportes/<int:pk>/editar/', views.editar_reporte, name='editar_reporte'),
    path('reportes/<int:pk>/eliminar/', views.eliminar_reporte, name='eliminar_reporte'),
    path('entradas/actualizar-volumen/', views.actualizar_volumen_carpeta, name='actualizar_volumen_carpeta'),
    path('materiales/actualizar-ubicacion/', views.actualizar_ubicacion_material, name='actualizar_ubicacion_material'),
    path('finanzas/cargar-csv/', views.cargar_partidas_csv, name='cargar_partidas_csv'),
    path('admin/whitelist/importar/', views.importar_whitelist, name='importar_whitelist'),

    # NUEVA RUTA:
    path('entradas/nueva/', views.crear_recepcion, name='crear_recepcion'),
    path('entradas/registrar/', views.registrar_entrada, name='registrar_entrada'),
    path('entradas/<int:pk>/editar/', views.editar_entrada, name='editar_entrada'),
    path('entradas/<int:pk>/eliminar/', views.eliminar_entrada, name='eliminar_entrada'),


    
    # NUEVAS RUTAS PARA SALIDAS (RIM):
    path('salidas/', views.lista_salidas, name='lista_salidas'),
    path('salidas/nueva/', views.crear_salida, name='crear_salida'),

    # NUEVA RUTA PARA EL PDF:
    path('salidas/pdf/<int:salida_id>/', views.generar_pdf_salida, name='generar_pdf_salida'),
    path('salidas/<int:pk>/editar/', views.editar_salida, name='editar_salida'),
    path('salidas/<int:pk>/eliminar/', views.eliminar_salida, name='eliminar_salida'),

    #NUEVA RUTAS 3
    path('guias/', views.lista_guias, name='lista_guias'),
    path('guias/nueva/', views.crear_guia, name='crear_guia'),
    path('guias/<int:pk>/editar/', views.editar_guia, name='editar_guia'),
    path('guias/<int:pk>/eliminar/', views.eliminar_guia, name='eliminar_guia'),
    path('guias/<int:guia_id>/', views.detalle_guia, name='detalle_guia'),
    path('guias/quitar-item/<int:item_id>/', views.quitar_de_guia, name='quitar_de_guia'),
    path('guia/<int:pk>/pdf/', views.generar_guia_pdf, name='generar_guia_pdf'),
    path('guia-transferencia/<int:guia_id>/pdf/', views.generar_pdf_transferencia, name='generar_pdf_transferencia'),

    # GUÍAS DE TRANSFERENCIA (ACTIVOS)
    path('guias/transferencia/nueva/', views.crear_guia_transferencia, name='crear_guia_transferencia'),
    path('guias/transferencia/<int:guia_id>/', views.detalle_guia_transferencia, name='detalle_guia_transferencia'),
    
    # API
    path('api/material/<int:material_id>/', views.get_material_info, name='api_material_info'),
    path('api/material/<int:material_id>/lotes/', views.api_lotes_material, name='api_lotes_material'),
    path('api/activo/<int:activo_id>/lotes/', views.api_lotes_activo, name='api_lotes_activo'),
    path('api/partidas/', views.api_partidas_por_departamento, name='api_partidas'),
    path('api/historial-odc/', views.api_historial_odc, name='api_historial_odc'),
    path('reportes/pdf/', views.generar_reporte_recepcion_pdf, name='generar_reporte_pdf'),
    
    # CONSUMO ANUAL 
    path('consumo-anual/', views.consumo_anual_vista, name='consumo_anual'),
    path('consumo-anual/excel/', views.exportar_consumo_anual_excel, name='exportar_consumo_anual_excel'),
    path('maestro/exportar/', views.exportar_inventario_maestro_excel, name='exportar_inventario_maestro'),
    path('entradas/exportar-excel/', views.exportar_entradas_excel, name='exportar_entradas_excel'),
    
    # GESTIÓN DE EQUIPO
    path('equipo/', views.gestion_equipo, name='gestion_equipo'),
    path('cambiar-contrasena/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('perfil/', views.perfil_usuario, name='perfil_usuario'),
]

# Servir archivos multimedia en desarrollo (DEBUG = True)
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
