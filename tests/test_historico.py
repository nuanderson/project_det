import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from core.models import AtualizacaoNotificacao, Notificacao
from core.services import importacao_pdf as imp

pytestmark = pytest.mark.django_db

DADOS = {
    "numero_det": "DET-1", "assunto": "Solicitação", "data_recebimento": "2026-09-10",
    "prazo_resposta": "2026-09-20", "status": "PENDENTE", "observacao": "",
}


def test_atualizacao_inicial_entra_no_historico(client, user_a):
    client.force_login(user_a)
    client.post(reverse("notificacao_criar"), {**DADOS, "atualizacao": "Recebida pela recepção em 10/09."})
    h = Notificacao.objects.get().atualizacoes.get()
    assert h.texto == "Recebida pela recepção em 10/09." and h.autor == user_a and h.origem == "MANUAL"


def test_sem_texto_nao_cria_linha_vazia_no_historico(client, user_a):
    client.force_login(user_a)
    client.post(reverse("notificacao_criar"), {**DADOS, "atualizacao": "   "})
    assert not AtualizacaoNotificacao.objects.exists()


def test_novas_atualizacoes_se_acumulam_sem_apagar_as_anteriores(client, user_a):
    client.force_login(user_a)
    client.post(reverse("notificacao_criar"), {**DADOS, "atualizacao": "Primeira"})
    n = Notificacao.objects.get()
    client.post(reverse("notificacao_editar", args=[n.pk]), {**DADOS, "atualizacao": "Segunda"})
    client.post(reverse("notificacao_editar", args=[n.pk]), {**DADOS, "atualizacao": "Terceira"})
    assert list(n.atualizacoes.order_by("id").values_list("texto", flat=True)) == ["Primeira", "Segunda", "Terceira"]
    html = client.get(reverse("notificacao_editar", args=[n.pk])).content.decode()
    assert "Primeira" in html and "Terceira" in html  # o formulário mostra o histórico


def test_mudar_status_na_edicao_gera_linha_automatica(client, user_a):
    client.force_login(user_a)
    client.post(reverse("notificacao_criar"), DADOS)
    n = Notificacao.objects.get()
    client.post(reverse("notificacao_editar", args=[n.pk]), {**DADOS, "status": "RESPONDIDA"})
    h = n.atualizacoes.get()
    assert h.origem == "STATUS" and "Pendente" in h.texto and "Respondida" in h.texto


def test_matriz_mudar_status_registra_no_historico(client, matriz, user_a, filial_a, criar_notificacao):
    n = criar_notificacao(filial_a, user_a)
    client.force_login(matriz)
    client.post(reverse("notificacao_status", args=[n.pk]), {"status": "EM_ANDAMENTO"})
    h = n.atualizacoes.get()
    assert h.autor == matriz and h.origem == "STATUS" and "Em andamento" in h.texto


def test_pdf_importado_aparece_anexado_e_entra_no_historico(client, monkeypatch, user_a):
    monkeypatch.setattr(imp, "extrair_texto", lambda arq: "AUTO DE INFRAÇÃO Nº 99.999.991-1\nNº Proc.:12345678901202617\nLocal:TERESINA/PI Data: 29/09/2026")
    client.force_login(user_a)
    pdf = SimpleUploadedFile("meu auto.pdf", b"%PDF-1.4 conteudo", content_type="application/pdf")
    resp = client.post(reverse("notificacao_importar"), {"pdf": pdf})
    html = resp.content.decode()
    assert "anexado automaticamente" in html and "meu auto.pdf" in html
    assert "meu auto.pdf" in resp.context["form"].fields["anexo"].help_text
    token = resp.context["importacao"]["token"]

    dados = {**DADOS, "importacao_token": token, "importacao_nome": "meu auto.pdf", "atualizacao": "Auto recebido na sede."}
    assert client.post(reverse("notificacao_criar"), dados).status_code == 302
    n = Notificacao.objects.get()
    assert n.anexo and n.anexo.read().startswith(b"%PDF")
    textos = {h.origem: h.texto for h in n.atualizacoes.all()}
    assert "meu auto.pdf" in textos["IMPORTACAO"] and textos["MANUAL"] == "Auto recebido na sede."


def test_erro_de_validacao_mantem_o_pdf_anexado_na_tela(client, monkeypatch, user_a):
    monkeypatch.setattr(imp, "extrair_texto", lambda arq: "AUTO DE INFRAÇÃO Nº 99.999.991-1\nNº Proc.:12345678901202617\nData: 29/09/2026")
    client.force_login(user_a)
    resp = client.post(reverse("notificacao_importar"), {"pdf": SimpleUploadedFile("a.pdf", b"%PDF-1.4 x", content_type="application/pdf")})
    token = resp.context["importacao"]["token"]
    invalido = {**DADOS, "assunto": "", "importacao_token": token, "importacao_nome": "a.pdf"}  # assunto obrigatório
    resp = client.post(reverse("notificacao_criar"), invalido)
    assert resp.status_code == 200 and "anexado automaticamente" in resp.content.decode()
    assert not Notificacao.objects.exists()
    corrigido = {**DADOS, "importacao_token": token, "importacao_nome": "a.pdf"}
    client.post(reverse("notificacao_criar"), corrigido)
    assert Notificacao.objects.get().anexo


def test_historico_nao_pode_ser_editado_nem_apagado(user_a, filial_a, criar_notificacao):
    n = criar_notificacao(filial_a, user_a)
    h = AtualizacaoNotificacao.objects.create(notificacao=n, autor=user_a, texto="x")
    h.texto = "alterado"
    with pytest.raises(ValidationError):
        h.save()
    with pytest.raises(ValidationError):
        h.delete()
    n.delete()  # excluir a notificação continua funcionando (cascata)
    assert not AtualizacaoNotificacao.objects.exists()


def test_detalhe_mostra_o_historico_para_filial_e_matriz(client, matriz, user_a, user_b, filial_a, criar_notificacao):
    n = criar_notificacao(filial_a, user_a)
    AtualizacaoNotificacao.objects.create(notificacao=n, autor=user_a, texto="Documentos separados")
    client.force_login(user_a)
    assert "Documentos separados" in client.get(reverse("notificacao_detalhe", args=[n.pk])).content.decode()
    client.force_login(matriz)
    assert "Documentos separados" in client.get(reverse("notificacao_detalhe", args=[n.pk])).content.decode()
    client.force_login(user_b)
    assert client.get(reverse("notificacao_detalhe", args=[n.pk])).status_code == 404
