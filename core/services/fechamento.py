from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from ..models import FechamentoMensal, JustificativaHistorico, LogAuditoria, obter_fechamento


def registrar_auditoria(usuario, acao, objeto, detalhe=""):
    LogAuditoria.objects.create(usuario=usuario, acao=acao, objeto=str(objeto), detalhe=detalhe)


def _checar_acesso(usuario, filial):
    if not usuario.is_matriz and usuario.filial_id != filial.pk:
        raise PermissionDenied("Sem acesso a esta filial.")


@transaction.atomic
def declarar_sem_notificacoes(usuario, filial, ano, mes):
    """A filial declara que não recebeu nada no mês. Só vale se não houver notificação cadastrada."""
    _checar_acesso(usuario, filial)
    fechamento = obter_fechamento(filial, ano, mes)
    fechamento.declarou_sem_notificacoes = True
    fechamento.save(update_fields=["declarou_sem_notificacoes", "atualizado_em"])
    fechamento.recalcular()
    registrar_auditoria(usuario, "declarar_sem_notificacoes", fechamento)
    return fechamento


@transaction.atomic
def desfazer_declaracao(usuario, filial, ano, mes):
    _checar_acesso(usuario, filial)
    fechamento = obter_fechamento(filial, ano, mes)
    fechamento.declarou_sem_notificacoes = False
    fechamento.save(update_fields=["declarou_sem_notificacoes", "atualizado_em"])
    fechamento.recalcular()
    registrar_auditoria(usuario, "desfazer_declaracao", fechamento)
    return fechamento


@transaction.atomic
def justificar(usuario, filial, ano, mes, texto):
    """Registra uma justificativa de não envio; o histórico é preservado (somente inserção)."""
    _checar_acesso(usuario, filial)
    texto = (texto or "").strip()
    if len(texto) < 10:
        raise ValidationError("Descreva a justificativa com pelo menos 10 caracteres.")
    fechamento = obter_fechamento(filial, ano, mes)
    JustificativaHistorico.objects.create(fechamento=fechamento, texto=texto, autor=usuario)
    fechamento.recalcular()
    registrar_auditoria(usuario, "justificar", fechamento, texto[:200])
    return fechamento


def situacao_do_mes(ano, mes, filiais=None):
    """Lista (filial, fechamento|None, situacao) de cada filial ativa no mês."""
    from ..models import Filial

    filiais = filiais if filiais is not None else Filial.objects.filter(ativa=True)
    fechamentos = {
        f.filial_id: f
        for f in FechamentoMensal.objects.filter(ano=ano, mes=mes).prefetch_related("justificativas__autor")
    }
    linhas = []
    for filial in filiais:
        fech = fechamentos.get(filial.pk)
        situacao = fech.situacao if fech else FechamentoMensal.Situacao.PENDENTE
        linhas.append({"filial": filial, "fechamento": fech, "situacao": situacao})
    return linhas
