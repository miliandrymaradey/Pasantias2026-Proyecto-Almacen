from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.shortcuts import render
from django.core.exceptions import ValidationError
from .models import CorreoAutorizado

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        # 1. Obtener el email del usuario de la sesión de inicio de sesión social
        user = sociallogin.user
        email = user.email
        
        # 2. Fallback defensivo a los campos típicos de Microsoft Azure AD en extra_data
        if not email and sociallogin.account:
            extra_data = sociallogin.account.extra_data or {}
            email = extra_data.get('mail') or extra_data.get('email') or extra_data.get('userPrincipalName')

        if email:
            email = email.strip().lower()
            # 3. Comprobar si el correo existe en la Lista Blanca (Whitelist)
            if CorreoAutorizado.objects.filter(email=email).exists():
                # Si existe en la Whitelist, se le permite continuar con el inicio de sesión social
                return
        
        # 4. Si el correo no está en la Lista Blanca o no se pudo extraer,
        # lanzamos una ImmediateHttpResponse para abortar la autenticación y mostrar la vista de acceso denegado.
        response = render(request, 'inventario/acceso_denegado.html', {'email': email})
        raise ImmediateHttpResponse(response)


class CustomAccountAdapter(DefaultAccountAdapter):
    def clean_email(self, email):
        email = email.strip().lower()
        # Buscar el email en la Lista Blanca (CorreoAutorizado)
        if not CorreoAutorizado.objects.filter(email=email).exists():
            raise ValidationError("Acceso Denegado: Su correo no está autorizado en Perforosven.")
        return email
