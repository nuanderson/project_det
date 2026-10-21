from ..models import AtualizacaoNotificacao


def registrar_atualizacao(notificacao, autor, texto, origem=AtualizacaoNotificacao.Origem.MANUAL):
    """Acrescenta uma linha ao histórico da notificação (nunca altera as anteriores)."""
    texto = (texto or "").strip()
    if not texto:
        return None
    return AtualizacaoNotificacao.objects.create(notificacao=notificacao, autor=autor, texto=texto, origem=origem)
