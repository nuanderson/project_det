"""Leitura de PDFs exportados do DET para pré-preencher o cadastro de notificações.

Por ora entende o Auto de Infração. O resultado é só uma sugestão: a pessoa confere e salva.
Dados pessoais de trabalhadores (listas de CPF) nunca são copiados para campos; ficam apenas no PDF anexado.
"""
import datetime
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from pypdf import PdfReader

from ..models import Filial, Notificacao

MAX_PAGINAS = 60
PASTA_TMP = "tmp_importacao"
_TOKEN = re.compile(r"^[0-9a-f]{32}$")


@dataclass
class DadosPDF:
    tipo: str = ""
    numero_det: str = ""
    assunto: str = ""
    data_recebimento: datetime.date | None = None
    cnpj: str = ""  # só dígitos
    numero_processo: str = ""
    notificacao_origem: str = ""
    local: str = ""
    # Mensagem da Caixa Postal do DET
    razao_social: str = ""
    remetente: str = ""
    data_hora: datetime.datetime | None = None
    ciencia: datetime.datetime | None = None
    sem_resposta: bool = False
    avisos: list = field(default_factory=list)

    @property
    def reconhecido(self):
        return bool(self.tipo)


def extrair_texto(arquivo):
    """Texto de todas as páginas; levanta ValueError se o arquivo não for um PDF legível."""
    try:
        arquivo.seek(0)
        leitor = PdfReader(arquivo)
        paginas = leitor.pages[:MAX_PAGINAS]
        return "\n".join((p.extract_text() or "") for p in paginas)
    except Exception as exc:  # pypdf levanta vários tipos para PDF corrompido ou criptografado
        raise ValueError("Não foi possível ler o PDF.") from exc
    finally:
        arquivo.seek(0)


def _sem_acento(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def _compactar(s):
    return re.sub(r"\s+", " ", s).strip()


_MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
          "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
_DATA_HORA = r"(\d{1,2})\s+([a-zç]{3})\.?\s+(\d{4})(?:\s+(\d{1,2}):(\d{2}))?"


def _data_hora(m):
    """Converte '21 set 2026 15:39' (grupos dia, mês abreviado, ano, hora, minuto) em datetime."""
    mes = _MESES.get(_sem_acento(m.group(2)))
    if not mes:
        return None
    try:
        return datetime.datetime(int(m.group(3)), mes, int(m.group(1)), int(m.group(4) or 0), int(m.group(5) or 0))
    except ValueError:
        return None


def _analisar_caixa_postal(texto):
    """Mensagem da Caixa Postal do DET (impressão da página): Empregador, Remetente, Assunto, Data e corpo."""
    d = DadosPDF()
    t = unicodedata.normalize("NFKC", texto)  # desfaz ligaduras do PDF (ﬁ -> fi)
    if not (re.search(r"^\s*Remetente:", t, re.M) and re.search(r"^\s*Assunto:", t, re.M)
            and re.search(r"^\s*Empregador:", t, re.M)):
        return d
    d.tipo = Notificacao.Tipo.COMUNICADO
    if m := re.search(r"^\s*Empregador:\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s*\|?\s*(.*)$", t, re.M):
        d.cnpj = re.sub(r"\D", "", m.group(1))
        d.razao_social = _compactar(m.group(2))
    if m := re.search(r"^\s*Remetente:\s*(.+)$", t, re.M):
        d.remetente = _compactar(m.group(1))
    if m := re.search(r"^\s*Assunto:\s*(.+?)\n\s*Data:", t, re.M | re.S):
        d.assunto = _compactar(m.group(1))
    if m := re.search(r"^\s*Data:\s*" + _DATA_HORA, t, re.M | re.I):
        d.data_hora = _data_hora(m)
        d.data_recebimento = d.data_hora.date() if d.data_hora else None
    if m := re.search(r"Data de Ci[eê]ncia:\s*" + _DATA_HORA, t, re.I):
        d.ciencia = _data_hora(m)
    d.sem_resposta = "nao ha opcao de resposta" in _sem_acento(t)
    # A mensagem não traz número: a data e hora de recebimento servem de identificação (editável).
    if d.data_hora:
        d.numero_det = f"CP {d.data_hora:%Y-%m-%d %H:%M}"
    for campo, rotulo in (("assunto", "assunto"), ("data_recebimento", "data"), ("cnpj", "CNPJ do empregador")):
        if not getattr(d, campo):
            d.avisos.append(f"Não foi possível identificar o {rotulo}; preencha manualmente.")
    return d


def analisar_texto(texto):
    d = DadosPDF()
    if not re.search(r"AUTO DE INFRA[ÇC][ÃA]O\s+N", texto, re.I):
        return _analisar_caixa_postal(texto)
    d.tipo = Notificacao.Tipo.AUTO_INFRACAO

    if m := re.search(r"AUTO DE INFRA[ÇC][ÃA]O\s+N[º°o.]*\s*([\d.]+-\d)", texto, re.I):
        d.numero_det = m.group(1)
    if m := re.search(r"CNPJ:\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", texto):
        d.cnpj = re.sub(r"\D", "", m.group(1))
    if m := re.search(r"N[º°o]\s*Proc\.?\s*:\s*(\d{10,})", texto):
        d.numero_processo = m.group(1)
    if m := re.search(r"Ementa:\s*\d+\s*\n\s*\d{6}-\d\s*\n(.+?)\nEMENTA\s*\(", texto, re.S):
        d.assunto = _compactar(m.group(1))
    if m := re.search(r"Local:\s*(.+?)\s+Data:\s*(\d{2})/(\d{2})/(\d{4})", texto):
        d.local = _compactar(m.group(1))
        try:
            d.data_recebimento = datetime.date(int(m.group(4)), int(m.group(3)), int(m.group(2)))
        except ValueError:
            pass
    # Notificação (NAD) que originou o auto: aparece no nome do arquivo anexo.
    if m := re.search(r"notificacao-([0-9A-Z]{10,20})\.pdf", texto, re.I):
        d.notificacao_origem = m.group(1).upper()

    for campo, rotulo in (("numero_det", "número do auto"), ("assunto", "ementa"),
                          ("data_recebimento", "data"), ("cnpj", "CNPJ")):
        if not getattr(d, campo):
            d.avisos.append(f"Não foi possível identificar o {rotulo}; preencha manualmente.")
    return d


def analisar_pdf(arquivo):
    return analisar_texto(extrair_texto(arquivo))


def filial_pelo_cnpj(cnpj):
    if not cnpj:
        return None
    for f in Filial.objects.all():
        if re.sub(r"\D", "", f.cnpj) == cnpj:
            return f
    return None


def filial_pela_cidade(local):
    """Sugestão fraca (município do 'Local:'): só vale se houver exatamente uma filial ativa na cidade."""
    cidade = _sem_acento(local.split("/")[0]) if local else ""
    if not cidade:
        return None
    achadas = [f for f in Filial.objects.filter(ativa=True) if _sem_acento(f.cidade) == cidade]
    return achadas[0] if len(achadas) == 1 else None


def sugerir(dados, usuario):
    """Valores iniciais do formulário + mensagens para a pessoa. Respeita o escopo do usuário."""
    inicial, msgs, erros = {}, [], []
    if not dados.reconhecido:
        msgs.append("Não reconheci o tipo deste PDF. O arquivo foi anexado; preencha os dados manualmente.")
        return inicial, msgs, erros

    inicial["tipo"] = dados.tipo
    if dados.numero_det:
        inicial["numero_det"] = dados.numero_det
    if dados.assunto:
        inicial["assunto"] = dados.assunto[:200]
    if dados.data_recebimento:
        inicial["data_recebimento"] = dados.data_recebimento
    if dados.numero_processo:
        inicial["numero_processo"] = dados.numero_processo
    if dados.cnpj:
        inicial["inscricao"] = dados.cnpj
    obs = []
    if dados.notificacao_origem:
        obs.append(f"Notificação de origem (NAD): {dados.notificacao_origem}")
    if dados.local:
        obs.append(f"Auto lavrado em: {dados.local}")
    if dados.remetente:
        obs.append(f"Remetente: {dados.remetente}")
    if dados.ciencia:
        obs.append(f"Ciência no DET em {dados.ciencia:%d/%m/%Y %H:%M}")
    if dados.sem_resposta:
        obs.append("Mensagem sem opção de resposta no DET (informativa).")
    if obs:
        inicial["observacao"] = "\n".join(obs)

    por_cnpj = filial_pelo_cnpj(dados.cnpj)
    if usuario.is_matriz:
        filial = por_cnpj or filial_pela_cidade(dados.local)
        if filial:
            inicial["filial"] = filial.pk
            if not por_cnpj:
                msgs.append(f"Filial sugerida pelo município ({filial.nome}); confira antes de salvar.")
        else:
            msgs.append("Não consegui identificar a filial pelo CNPJ do documento. Escolha a filial.")
    elif por_cnpj and por_cnpj.pk != usuario.filial_id:
        erros.append(f"Este documento é do CNPJ da filial {por_cnpj.nome}. Importe-o pela própria filial.")

    if dados.numero_det:
        filial_id = inicial.get("filial") or usuario.filial_id
        if filial_id and Notificacao.objects.filter(filial_id=filial_id, numero_det=dados.numero_det).exists():
            msgs.append(f"Atenção: já existe uma notificação {dados.numero_det} para esta filial.")
    msgs.extend(dados.avisos)
    if dados.tipo == Notificacao.Tipo.COMUNICADO:
        msgs.append("A mensagem não traz número; usei a data e hora de recebimento como identificação (você pode trocar).")
        if dados.sem_resposta:
            msgs.append("Esta mensagem é informativa e não admite resposta no DET. Se não exigir providência, marque como Respondida.")
        msgs.append("O prazo de resposta não consta na mensagem; informe-o se a mensagem exigir providência.")
    else:
        msgs.append("O prazo de resposta e o código de acesso ao processo não constam no PDF; preencha se tiver.")
    return inicial, msgs, erros


# ---------- arquivo temporário entre a leitura e o salvamento ----------

def guardar_temporario(arquivo):
    token = uuid.uuid4().hex
    arquivo.seek(0)
    default_storage.save(f"{PASTA_TMP}/{token}.pdf", ContentFile(arquivo.read()))
    return token


def _caminho(token):
    if not _TOKEN.match(token or ""):
        return None
    return f"{PASTA_TMP}/{token}.pdf"


def abrir_temporario(token, nome="documento-det.pdf"):
    caminho = _caminho(token)
    if not caminho or not default_storage.exists(caminho):
        return None
    with default_storage.open(caminho, "rb") as f:
        return ContentFile(f.read(), name=Path(nome).name)


def descartar_temporario(token):
    caminho = _caminho(token)
    if caminho and default_storage.exists(caminho):
        default_storage.delete(caminho)
