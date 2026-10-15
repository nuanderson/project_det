"""Consultas agregadas do dashboard, separadas das views para serem testáveis."""

import datetime

from django.db.models import Count, Q
from django.db.models.functions import ExtractMonth
from django.utils import timezone

from ..models import Filial, FechamentoMensal, Notificacao
from .fechamento import situacao_do_mes

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def resumo(ano, mes, hoje=None, qs=None):
    hoje = hoje or timezone.localdate()
    qs = Notificacao.objects.all() if qs is None else qs
    do_ano = qs.filter(data_recebimento__year=ano)
    do_mes = do_ano.filter(data_recebimento__month=mes)
    limite = hoje + datetime.timedelta(days=7)
    abertas = qs.abertas()
    return {
        "total_ano": do_ano.count(),
        "total_mes": do_mes.count(),
        "pendentes": abertas.filter(status=Notificacao.Status.PENDENTE).count(),
        "em_andamento": abertas.filter(status=Notificacao.Status.EM_ANDAMENTO).count(),
        "respondidas": qs.filter(status=Notificacao.Status.RESPONDIDA).count(),
        "vencidas": qs.vencidas(hoje).count(),
        "prazo_7_dias": abertas.filter(prazo_resposta__gte=hoje, prazo_resposta__lte=limite).count(),
    }


def serie_mensal(ano, qs=None):
    qs = Notificacao.objects.all() if qs is None else qs
    contagens = {
        r["m"]: r["n"]
        for r in qs.filter(data_recebimento__year=ano)
        .annotate(m=ExtractMonth("data_recebimento"))
        .values("m")
        .annotate(n=Count("id"))
    }
    return [{"mes": MESES[i], "total": contagens.get(i + 1, 0)} for i in range(12)]


def por_filial(ano, mes, hoje=None):
    hoje = hoje or timezone.localdate()
    filiais = Filial.objects.filter(ativa=True).annotate(
        total_ano=Count("notificacoes", filter=Q(notificacoes__data_recebimento__year=ano), distinct=True),
        total_mes=Count(
            "notificacoes",
            filter=Q(notificacoes__data_recebimento__year=ano, notificacoes__data_recebimento__month=mes),
            distinct=True,
        ),
        vencidas=Count(
            "notificacoes",
            filter=Q(notificacoes__prazo_resposta__lt=hoje) & ~Q(notificacoes__status=Notificacao.Status.RESPONDIDA),
            distinct=True,
        ),
    )
    situacoes = {l["filial"].pk: l["situacao"] for l in situacao_do_mes(ano, mes, filiais)}
    rotulos = dict(FechamentoMensal.Situacao.choices)
    return [
        {
            "filial": f,
            "total_ano": f.total_ano,
            "total_mes": f.total_mes,
            "vencidas": f.vencidas,
            "situacao": situacoes[f.pk],
            "situacao_rotulo": rotulos[situacoes[f.pk]],
        }
        for f in filiais
    ]


def conformidade(ano, mes):
    """Quantas filiais ativas estão em cada situação no mês."""
    contagem = {valor: 0 for valor, _ in FechamentoMensal.Situacao.choices}
    for linha in situacao_do_mes(ano, mes):
        contagem[linha["situacao"]] += 1
    return contagem


def dados_completos(ano, mes, hoje=None):
    filiais = por_filial(ano, mes, hoje)
    return {
        "ano": ano,
        "mes": mes,
        "resumo": resumo(ano, mes, hoje),
        "serie": serie_mensal(ano),
        "filiais": filiais,
        "conformidade": conformidade(ano, mes),
        "nao_enviaram": [f for f in filiais if f["situacao"] in ("PENDENTE", "JUSTIFICADO")],
    }
