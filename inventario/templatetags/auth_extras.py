from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_names):
    """
    Filtro para verificar en las plantillas HTML si un usuario pertenece a uno
    de los grupos especificados (separados por comas). 
    Ejemplo: {% if request.user|has_group:"Coordinador de Almacén,Especialista de Activos" %}
    """
    if not user or not user.is_authenticated:
        return False
        
    # Los superusuarios (como el Coordinador de Almacén) tienen acceso a todo automáticamente
    if user.is_superuser:
        return True

    # Dividir la cadena de nombres de grupos separados por comas y limpiar espacios
    groups_list = [g.strip() for g in group_names.split(',')]
    
    # Comprobar pertenencia a cualquiera de los grupos
    return user.groups.filter(name__in=groups_list).exists()
