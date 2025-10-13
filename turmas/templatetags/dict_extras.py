# turmas/templatetags/dict_extras.py
from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    """
    Uso no template: {{ meu_dict|get_item:chave }}
    Retorna d.get(chave, "") se d for dict; caso contrário, retorna "".
    """
    try:
        return d.get(key, "")
    except Exception:
        return ""
