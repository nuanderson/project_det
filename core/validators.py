from django.conf import settings
from django.core.exceptions import ValidationError


def validar_anexo(arquivo):
    nome = arquivo.name.lower()
    if not nome.endswith(tuple(settings.ANEXO_EXTENSOES)):
        permitidas = ", ".join(settings.ANEXO_EXTENSOES)
        raise ValidationError(f"Tipo de arquivo não permitido. Use: {permitidas}.")
    limite = settings.ANEXO_MAX_MB * 1024 * 1024
    if arquivo.size > limite:
        raise ValidationError(f"Arquivo maior que {settings.ANEXO_MAX_MB} MB.")
