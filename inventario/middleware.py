from django.shortcuts import redirect
from django.urls import reverse

class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Operar solo si el usuario está autenticado
        if request.user.is_authenticated:
            # Rutas seguras excluidas para evitar bucle de redirección infinita
            path_cambiar_clave = reverse('password_change')
            path_logout = reverse('logout')
            
            # Permitir libre acceso a la página de cambio de clave, cierre de sesión y recursos estáticos
            if request.path != path_cambiar_clave and request.path != path_logout and not request.path.startswith('/static/') and not request.path.startswith('/media/'):
                # Consultar la sesión primero para evitar consultas a la base de datos
                debe_cambiar = request.session.get('debe_cambiar_clave')
                
                if debe_cambiar is None:
                    try:
                        # Intentar acceder a la relación directa que Django almacena en caché
                        perfil = request.user.perfil
                    except Exception:
                        # Si no existe (caso de usuarios históricos creados sin perfil), se crea de forma segura
                        from inventario.models import PerfilUsuario
                        perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)
                    
                    debe_cambiar = perfil.debe_cambiar_clave
                    request.session['debe_cambiar_clave'] = debe_cambiar
                
                # Redirigir de forma obligatoria si el flag debe_cambiar_clave es True
                if debe_cambiar:
                    return redirect('password_change')

        response = self.get_response(request)
        return response
