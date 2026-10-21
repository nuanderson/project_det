import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def asset(caminho):
    """URL do arquivo estático com a data de modificação (?v=...), para o navegador nunca usar uma versão velha."""
    url = static(caminho)
    arquivo = finders.find(caminho)
    if arquivo and os.path.exists(arquivo):
        return f"{url}?v={int(os.path.getmtime(arquivo))}"
    return url
