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
                from inventario.models import PerfilUsuario
                perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)
                
                # Redirigir de forma obligatoria si el flag debe_cambiar_clave es True
                if perfil.debe_cambiar_clave:
                    return redirect('password_change')

        response = self.get_response(request)
        return response
