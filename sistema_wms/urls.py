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
from django.urls import path
from django.contrib.auth import views as auth_views
from inventario import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- RUTAS DE SEGURIDAD (LOGIN/LOGOUT) --- <- NUEVO
    path('login/', auth_views.LoginView.as_view(template_name='inventario/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', views.dashboard, name='dashboard'), # La página principal ahora es el Dashboard
    path('maestro/', views.lista_materiales, name='lista_materiales'),

    # NUEVA RUTA AQUI
    path('entradas/', views.lista_entradas, name='lista_entradas'),
    path('entradas/procura/', views.data_procura, name='data_procura'),

    # NUEVA RUTA:
    path('entradas/nueva/', views.crear_recepcion, name='crear_recepcion'),

    # NUEVA RUTA:
    path('entradas/<int:reporte_id>/', views.detalle_recepcion, name='detalle_recepcion'),
    
    # NUEVAS RUTAS PARA SALIDAS (RIM):
    path('salidas/', views.lista_salidas, name='lista_salidas'),
    path('salidas/nueva/', views.crear_salida, name='crear_salida'),

    # NUEVA RUTA PARA EL PDF:
    path('salidas/pdf/<int:salida_id>/', views.generar_pdf_salida, name='generar_pdf_salida'),

    #NUEVA RUTAS 3
    path('guias/', views.lista_guias, name='lista_guias'),
    path('guias/nueva/', views.crear_guia, name='crear_guia'),
    path('guias/<int:guia_id>/', views.detalle_guia, name='detalle_guia'),
    path('guias/pdf/<int:guia_id>/', views.generar_pdf_guia, name='generar_pdf_guia'),
]


