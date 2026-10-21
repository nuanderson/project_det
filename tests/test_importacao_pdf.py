import datetime
import re
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from core.models import Filial, Notificacao
from core.services import importacao_pdf as imp

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures"

# Texto sintético no layout do Auto de Infração (sem dados pessoais).
TEXTO_AUTO = """ÓRGÃO REGIONAL:
CNPJ:11.222.333/0039-72Inscrição: CNPJ:11.222.333/0039-72
AUTO DE INFRAÇÃO Nº 99.999.991-1
Nº Proc.:12345678901202617
Ementa: 0011681
001168-1
Deixar de apresentar documentos sujeitos à inspeção do trabalho no dia  e  hora
previamente fixados pelo AFT.
EMENTA (Nº/Descrição):
        Foi lavrada Notificação (NAD) nº 9X9X9X9X9X9X99 em 15.6.2026.
109 - Arquivo "relatorio-atendimento-9X9X9X9X9X9X99.pdf" (Relatório)
108 - Arquivo "notificacao-9X9X9X9X9X9X99.pdf" (Notificação Inicial)
Local:TERESINA/PI Data: 29/09/2026
"""


def test_analisa_auto_de_infracao():
    d = imp.analisar_texto(TEXTO_AUTO)
    assert d.tipo == Notificacao.Tipo.AUTO_INFRACAO
    assert d.numero_det == "99.999.991-1"
    assert d.cnpj == "11222333003972"
    assert d.numero_processo == "12345678901202617"
    assert d.assunto.startswith("Deixar de apresentar documentos") and d.assunto.endswith("pelo AFT.")
    assert d.data_recebimento == datetime.date(2026, 9, 29)
    assert d.notificacao_origem == "9X9X9X9X9X9X99"
    assert d.local == "TERESINA/PI"


def test_texto_desconhecido_nao_e_reconhecido():
    d = imp.analisar_texto("Qualquer outro documento qualquer")
    assert not d.reconhecido


def test_link_do_processo_monta_com_os_tres_dados(filial_a, user_a):
    n = Notificacao(filial=filial_a, numero_det="X", assunto="a", data_recebimento=datetime.date.today(),
                    criado_por=user_a, numero_processo="12345678902202616", inscricao="11222333000108")
    assert n.link_processo == ""  # falta o código de acesso
    n.codigo_acesso = "ABCD1234"
    assert n.link_processo == (
        "https://eprocesso.sit.trabalho.gov.br/Paginas/ConsultaProcesso"
        "?NrProcesso=12345678902202616&NrInscricao=11222333000108&CdAcesso=ABCD1234"
    )


def _pdf(conteudo=b"%PDF-1.4 x", nome="auto.pdf"):
    return SimpleUploadedFile(nome, conteudo, content_type="application/pdf")


def _importar_texto(monkeypatch, texto=TEXTO_AUTO):
    monkeypatch.setattr(imp, "extrair_texto", lambda arq: texto)


def test_importar_preenche_formulario_para_a_filial(client, monkeypatch, user_a, filial_a):
    filial_a.cnpj = "11.222.333/0039-72"
    filial_a.save()
    _importar_texto(monkeypatch)
    client.force_login(user_a)
    resp = client.post(reverse("notificacao_importar"), {"pdf": _pdf()})
    assert resp.status_code == 200
    f = resp.context["form"]
    assert f.initial["numero_det"] == "99.999.991-1" and f.initial["tipo"] == "AUTO_INFRACAO"
    assert f.initial["inscricao"] == "11222333003972" and f.initial["data_recebimento"] == datetime.date(2026, 9, 29)
    assert "9X9X9X9X9X9X99" in f.initial["observacao"]
    assert resp.context["importacao"]["token"]


def test_salvar_anexa_o_pdf_importado_sem_novo_upload(client, monkeypatch, user_a):
    _importar_texto(monkeypatch)
    client.force_login(user_a)
    resp = client.post(reverse("notificacao_importar"), {"pdf": _pdf(b"%PDF-1.4 conteudo", "meu auto.pdf")})
    token = resp.context["importacao"]["token"]
    dados = {
        "importacao_token": token, "importacao_nome": "meu auto.pdf", "tipo": "AUTO_INFRACAO",
        "numero_det": "99.999.991-1", "assunto": "Deixar de apresentar", "data_recebimento": "2026-09-29",
        "prazo_resposta": "", "status": "PENDENTE", "numero_processo": "12345678901202617",
        "inscricao": "11.222.333/0039-72", "codigo_acesso": "abcd1234", "observacao": "",
    }
    resp = client.post(reverse("notificacao_criar"), dados)
    assert resp.status_code == 302
    n = Notificacao.objects.get()
    assert n.anexo and n.anexo.read().startswith(b"%PDF") and n.tipo == "AUTO_INFRACAO"
    assert n.inscricao == "11222333003972" and n.codigo_acesso == "ABCD1234"
    assert n.link_processo.endswith("CdAcesso=ABCD1234")
    # o temporário é descartado e não pode ser reutilizado
    assert imp.abrir_temporario(token) is None


def test_token_de_outra_sessao_e_ignorado(client, user_a):
    token = imp.guardar_temporario(_pdf())
    client.force_login(user_a)
    dados = {"importacao_token": token, "tipo": "NOTIFICACAO", "numero_det": "1", "assunto": "a",
             "data_recebimento": "2026-01-10", "status": "PENDENTE"}
    client.post(reverse("notificacao_criar"), dados)
    assert not Notificacao.objects.get().anexo


def test_filial_nao_importa_documento_de_outra_filial(client, monkeypatch, user_a, filial_b):
    filial_b.cnpj = "11.222.333/0039-72"
    filial_b.save()
    _importar_texto(monkeypatch)
    client.force_login(user_a)
    resp = client.post(reverse("notificacao_importar"), {"pdf": _pdf()})
    assert resp.status_code == 200 and "pdf" in resp.context["form"].errors
    assert "importacao" not in resp.context


def test_filial_aceita_documento_com_cnpj_da_sede(client, monkeypatch, user_a):
    # CNPJ do documento não pertence a nenhuma filial cadastrada (ex.: sede): a filial pode importar.
    _importar_texto(monkeypatch)
    client.force_login(user_a)
    resp = client.post(reverse("notificacao_importar"), {"pdf": _pdf()})
    assert resp.context["importacao"]["token"]


def test_matriz_recebe_filial_sugerida_pelo_cnpj(client, monkeypatch, matriz, filial_b):
    filial_b.cnpj = "11.222.333/0039-72"
    filial_b.save()
    _importar_texto(monkeypatch)
    client.force_login(matriz)
    resp = client.post(reverse("notificacao_importar"), {"pdf": _pdf()})
    assert resp.context["form"].initial["filial"] == filial_b.pk


def test_matriz_sem_cnpj_conhecido_escolhe_a_filial(client, monkeypatch, matriz, filial_a):
    _importar_texto(monkeypatch)
    client.force_login(matriz)
    resp = client.post(reverse("notificacao_importar"), {"pdf": _pdf()})
    assert "filial" not in resp.context["form"].initial


def test_sugestao_pelo_municipio_so_com_filial_unica():
    Filial.objects.create(nome="PG", cnpj="33.333.333/0001-33", cidade="Ponta Grossa")
    assert imp.filial_pela_cidade("PONTA GROSSA/PR").nome == "PG"
    Filial.objects.create(nome="PG2", cnpj="44.444.444/0001-44", cidade="Ponta Grossa")
    assert imp.filial_pela_cidade("PONTA GROSSA/PR") is None


def test_pdf_ilegivel_mostra_erro_e_nao_quebra(client, user_a):
    client.force_login(user_a)
    resp = client.post(reverse("notificacao_importar"), {"pdf": _pdf(b"%PDF-1.4 quebrado")})
    assert resp.status_code == 200 and "pdf" in resp.context["form"].errors


def test_importar_rejeita_arquivo_que_nao_e_pdf(client, user_a):
    client.force_login(user_a)
    resp = client.post(reverse("notificacao_importar"), {"pdf": _pdf(b"MZ nao e pdf", "a.pdf")})
    assert "pdf" in resp.context["form"].errors


def test_importar_exige_login(client):
    assert client.get(reverse("notificacao_importar")).status_code == 302


# ---------- PDFs reais (contêm dados pessoais; ficam só na máquina, fora do git) ----------

real = pytest.mark.skipif(not (FIXTURES / "auto_sede.pdf").exists(), reason="PDFs reais não disponíveis")
ARQUIVOS_REAIS = ["auto_agua_branca.pdf", "auto_sede.pdf"]


@real
@pytest.mark.parametrize("arquivo", ARQUIVOS_REAIS)
def test_pdfs_reais_sao_lidos_no_formato_esperado(arquivo):
    with open(FIXTURES / arquivo, "rb") as f:
        d = imp.analisar_pdf(f)
    assert re.fullmatch(r"\d{2}\.\d{3}\.\d{3}-\d", d.numero_det)
    assert re.fullmatch(r"\d{14}", d.cnpj) and re.fullmatch(r"\d{17}", d.numero_processo)
    assert d.data_recebimento and d.assunto and d.local


@real
@pytest.mark.parametrize("arquivo", ARQUIVOS_REAIS)
def test_dados_pessoais_dos_trabalhadores_nao_vao_para_os_campos(arquivo):
    with open(FIXTURES / arquivo, "rb") as f:
        d = imp.analisar_pdf(f)
    campos = " ".join([d.assunto, d.local, d.numero_det, d.notificacao_origem or ""])
    assert not re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", campos)  # nenhum CPF
