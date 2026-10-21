import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from core.services import dashboard as dash

pytestmark = pytest.mark.django_db


def _numeros(client, **filtros):
    resp = client.get(reverse("notificacao_lista"), filtros)
    return {n.numero_det for n in resp.context["notificacoes"]}


def test_filtro_prazo_7_dias_bate_com_o_card_do_dashboard(client, matriz, user_a, filial_a, criar_notificacao, hoje, dias):
    criar_notificacao(filial_a, user_a, prazo=hoje + dias(3), numero="P3")
    criar_notificacao(filial_a, user_a, prazo=hoje + dias(7), numero="P7")
    criar_notificacao(filial_a, user_a, prazo=hoje + dias(8), numero="P8")       # fora da janela
    criar_notificacao(filial_a, user_a, prazo=hoje - dias(1), numero="VENC")     # já vencida
    criar_notificacao(filial_a, user_a, prazo=hoje + dias(2), status="RESPONDIDA", numero="RESP")
    client.force_login(matriz)
    assert _numeros(client, prazo="7") == {"P3", "P7"}
    assert dash.resumo(hoje.year, hoje.month)["prazo_7_dias"] == 2


@pytest.mark.parametrize("filtro, card", [
    ({"status": "VENCIDA"}, "vencidas"),
    ({"status": "PENDENTE"}, "pendentes"),
    ({"status": "EM_ANDAMENTO"}, "em_andamento"),
    ({"status": "RESPONDIDA"}, "respondidas"),
])
def test_cada_card_leva_a_uma_lista_com_o_mesmo_total(client, matriz, user_a, filial_a, criar_notificacao, hoje, dias, filtro, card):
    criar_notificacao(filial_a, user_a, prazo=hoje - dias(2), status="PENDENTE", numero="A")
    criar_notificacao(filial_a, user_a, prazo=hoje + dias(5), status="PENDENTE", numero="B")
    criar_notificacao(filial_a, user_a, status="EM_ANDAMENTO", numero="C")
    criar_notificacao(filial_a, user_a, prazo=hoje - dias(9), status="EM_ANDAMENTO", numero="D")
    criar_notificacao(filial_a, user_a, status="RESPONDIDA", numero="E")
    client.force_login(matriz)
    esperado = dash.resumo(hoje.year, hoje.month)[card]
    assert len(_numeros(client, **filtro)) == esperado


def test_dashboard_tem_cards_clicaveis_para_a_lista_filtrada(client, matriz):
    client.force_login(matriz)
    html = client.get(reverse("dashboard")).content.decode()
    lista = reverse("notificacao_lista")
    for sufixo in ("?status=VENCIDA", "?prazo=7", "?status=PENDENTE", "?status=EM_ANDAMENTO", "?status=RESPONDIDA"):
        assert f'href="{lista}{sufixo}"' in html
    ano = timezone.localdate().year
    assert f'href="{lista}?ano={ano}"' in html


def test_dashboard_tem_alternativa_em_texto_para_os_graficos(client, matriz):
    client.force_login(matriz)
    html = client.get(reverse("dashboard")).content.decode()
    assert html.count('role="img"') == 2 and "visually-hidden" in html
    assert "Com notificações" in html and "Pendente" in html


def test_dashboard_sem_filiais_mostra_estado_vazio(client, matriz):
    client.force_login(matriz)
    assert "Nenhuma filial cadastrada" in client.get(reverse("dashboard")).content.decode()


def test_limpar_filtros_aparece_so_quando_ha_filtro(client, matriz):
    client.force_login(matriz)
    sem = client.get(reverse("notificacao_lista")).content.decode()
    com = client.get(reverse("notificacao_lista"), {"status": "PENDENTE"}).content.decode()
    assert "Limpar filtros" not in sem and "Limpar filtros" in com
    assert "Nenhuma notificação registrada" in sem
    assert "Nenhuma notificação neste período ou filtro" in com


def test_filtro_prazo_mostra_chip_e_nao_quebra_com_valor_invalido(client, matriz):
    client.force_login(matriz)
    assert "Prazo nos próximos 7 dias" in client.get(reverse("notificacao_lista"), {"prazo": "7"}).content.decode()
    assert client.get(reverse("notificacao_lista"), {"prazo": "99", "mes": "abc"}).status_code == 200


def test_menu_hamburguer_so_para_quem_esta_logado(client, user_a):
    html_login = client.get(reverse("login")).content.decode()
    assert "menu-lateral" not in html_login
    client.force_login(user_a)
    html = client.get(reverse("painel")).content.decode()
    assert 'data-bs-target="#menu-lateral"' in html and 'aria-controls="menu-lateral"' in html
    assert 'aria-current="page"' in html and 'href="#conteudo"' in html
