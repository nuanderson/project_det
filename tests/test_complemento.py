import datetime

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _url(n):
    return reverse("notificacao_complemento", args=[n.pk])


def test_matriz_define_o_prazo_e_ele_entra_no_historico(client, matriz, user_a, filial_a, criar_notificacao, hoje, dias):
    n = criar_notificacao(filial_a, user_a, data=hoje - dias(2))
    client.force_login(matriz)
    prazo = hoje + dias(10)
    resp = client.post(_url(n), {"prazo_resposta": prazo.isoformat(), "codigo_acesso": ""})
    assert resp.status_code == 302
    n.refresh_from_db()
    assert n.prazo_resposta == prazo
    h = n.atualizacoes.get()
    assert h.origem == "COMPLEMENTO" and h.autor == matriz and f"{prazo:%d/%m/%Y}" in h.texto


def test_alterar_o_prazo_registra_de_para_e_prazo_vencido_aparece_como_vencida(client, matriz, user_a, filial_a, criar_notificacao, hoje, dias):
    n = criar_notificacao(filial_a, user_a, data=hoje - dias(30), prazo=hoje + dias(5))
    client.force_login(matriz)
    novo = hoje - dias(1)
    client.post(_url(n), {"prazo_resposta": novo.isoformat(), "codigo_acesso": ""})
    n.refresh_from_db()
    assert n.vencida
    assert "alterado de" in n.atualizacoes.get().texto


def test_prazo_anterior_ao_recebimento_e_recusado(client, matriz, user_a, filial_a, criar_notificacao, hoje, dias):
    n = criar_notificacao(filial_a, user_a, data=hoje)
    client.force_login(matriz)
    client.post(_url(n), {"prazo_resposta": (hoje - dias(1)).isoformat(), "codigo_acesso": ""})
    n.refresh_from_db()
    assert n.prazo_resposta is None and not n.atualizacoes.exists()


def test_codigo_de_acesso_libera_o_link_sem_gravar_o_codigo_no_historico(client, matriz, user_a, filial_a, criar_notificacao):
    n = criar_notificacao(filial_a, user_a)
    n.numero_processo, n.inscricao = "12345678901202617", "11222333000181"
    n.save()
    client.force_login(matriz)
    client.post(_url(n), {"prazo_resposta": "", "codigo_acesso": "abcd1234"})
    n.refresh_from_db()
    assert n.codigo_acesso == "ABCD1234" and n.link_processo.endswith("CdAcesso=ABCD1234")
    texto = n.atualizacoes.get().texto
    assert "informado" in texto and "ABCD1234" not in texto
    client.post(_url(n), {"prazo_resposta": "", "codigo_acesso": "x!"})  # inválido: nada muda
    n.refresh_from_db()
    assert n.codigo_acesso == "ABCD1234"


def test_so_prazo_e_codigo_mudam_o_resto_fica_intacto(client, matriz, user_a, filial_a, criar_notificacao, hoje, dias):
    n = criar_notificacao(filial_a, user_a, numero="A1")
    client.force_login(matriz)
    client.post(_url(n), {"prazo_resposta": (hoje + dias(3)).isoformat(), "codigo_acesso": "", "assunto": "HACK", "status": "RESPONDIDA", "numero_det": "X"})
    n.refresh_from_db()
    assert n.assunto == "Assunto" and n.status == "PENDENTE" and n.numero_det == "A1"


def test_sem_mudanca_nao_cria_historico(client, matriz, user_a, filial_a, criar_notificacao, hoje, dias):
    n = criar_notificacao(filial_a, user_a, prazo=hoje + dias(3))
    client.force_login(matriz)
    client.post(_url(n), {"prazo_resposta": (hoje + dias(3)).isoformat(), "codigo_acesso": ""})
    assert not n.atualizacoes.exists()


def test_filial_nao_pode_usar_o_complemento(client, user_a, filial_a, criar_notificacao, hoje, dias):
    n = criar_notificacao(filial_a, user_a)
    client.force_login(user_a)
    assert client.post(_url(n), {"prazo_resposta": (hoje + dias(3)).isoformat(), "codigo_acesso": ""}).status_code == 302
    n.refresh_from_db()
    assert n.prazo_resposta is None


def test_detalhe_mostra_o_cartao_so_para_a_matriz(client, matriz, user_a, filial_a, criar_notificacao):
    n = criar_notificacao(filial_a, user_a)
    client.force_login(matriz)
    html = client.get(reverse("notificacao_detalhe", args=[n.pk])).content.decode()
    assert "Complementar dados" in html and 'name="prazo_resposta"' in html
    client.force_login(user_a)
    assert "Complementar dados" not in client.get(reverse("notificacao_detalhe", args=[n.pk])).content.decode()
