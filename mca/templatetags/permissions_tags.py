from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """Retorna True se o usuário pertence ao grupo informado."""
    return user.groups.filter(name=group_name).exists()
