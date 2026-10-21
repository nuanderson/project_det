from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from ..models import AtualizacaoNotificacao, AvisoNotificacao, Notificacao
from .fechamento import registrar_auditoria
from .historico import registrar_atualizacao


def emails_filial(filial):
    destinos = {filial.email} if filial.email else set()
    destinos |= set(filial.usuarios.filter(is_active=True).exclude(email="").values_list("email", flat=True))
    return sorted(destinos)


@transaction.atomic
def mudar_status(usuario, notificacao, novo_status):
    """Matriz altera só o status; o conteúdo enviado pela filial não é tocado."""
    if not usuario.is_matriz:
        raise PermissionDenied("Somente a matriz altera o status por esta ação.")
    if novo_status not in Notificacao.Status.values:
        raise ValueError("Status inválido.")
    anterior = notificacao.status
    if anterior != novo_status:
        notificacao.status = novo_status
        notificacao.save(update_fields=["status", "atualizado_em"])
        registrar_auditoria(usuario, "mudar_status", notificacao, f"{anterior} -> {novo_status}")
        rotulos = dict(Notificacao.Status.choices)
        registrar_atualizacao(
            notificacao, usuario, f"Status alterado de {rotulos[anterior]} para {rotulos[novo_status]}.",
            AtualizacaoNotificacao.Origem.STATUS,
        )
    return notificacao


@transaction.atomic
def enviar_aviso(usuario, notificacao, tipo, texto=""):
    """Registra o aviso para a filial e avisa por e-mail (se houver destinatário)."""
    if not usuario.is_matriz:
        raise PermissionDenied("Somente a matriz envia avisos.")
    aviso = AvisoNotificacao(notificacao=notificacao, tipo=tipo, texto=(texto or "").strip(), autor=usuario)
    aviso.full_clean(exclude=["autor", "notificacao"])
    aviso.save()
    registrar_auditoria(usuario, "enviar_aviso", notificacao, f"{aviso.get_tipo_display()}: {aviso.texto[:200]}")

    destinos = emails_filial(notificacao.filial)
    if destinos:
        corpo = (
            f"A matriz marcou a notificação {notificacao.numero_det} ({notificacao.assunto}) "
            f"como: {aviso.get_tipo_display()}.\n"
        )
        if aviso.texto:
            corpo += f"\n{aviso.texto}\n"
        corpo += "\nAcesse o sistema para ver os detalhes."
        send_mail(
            f"Controle DET: notificação {notificacao.numero_det} - {aviso.get_tipo_display()}",
            corpo, settings.DEFAULT_FROM_EMAIL, destinos, fail_silently=True,
        )
    return aviso


def marcar_avisos_lidos(usuario, notificacao):
    if not usuario.is_matriz:
        notificacao.avisos.filter(lido_em__isnull=True).update(lido_em=timezone.now())


def avisos_nao_lidos(filial):
    return AvisoNotificacao.objects.filter(notificacao__filial=filial, lido_em__isnull=True).select_related("notificacao")
