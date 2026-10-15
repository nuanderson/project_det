from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (
    AvisoForm, FilialForm, FiltroNotificacaoForm, JustificativaForm, NotificacaoForm, StatusForm, UsuarioForm,
)
from .models import AvisoNotificacao, Filial, Notificacao, Usuario, obter_fechamento
from .services import avisos as avisos_service
from .services import dashboard as dash
from .services import exportacao, fechamento as fech

matriz_required = user_passes_test(lambda u: u.is_authenticated and u.is_matriz, login_url="login")


def _competencia(request):
    hoje = timezone.localdate()
    try:
        ano = int(request.GET.get("ano", hoje.year))
        mes = int(request.GET.get("mes", hoje.month))
    except ValueError:
        return hoje.year, hoje.month
    if not (2000 <= ano <= 2100 and 1 <= mes <= 12):
        return hoje.year, hoje.month
    return ano, mes


def _voltar(request):
    """Redireciona para `next` apenas se for um caminho interno (evita open redirect)."""
    destino = request.POST.get("next", "")
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect("home")


def _filtrar_notificacoes(request):
    qs = Notificacao.objects.visiveis_para(request.user).select_related("filial")
    form = FiltroNotificacaoForm(request.GET or None)
    if form.is_valid():
        d = form.cleaned_data
        if d["filial"] and request.user.is_matriz:
            qs = qs.filter(filial=d["filial"])
        if d["ano"]:
            qs = qs.filter(data_recebimento__year=d["ano"])
        if d["mes"]:
            qs = qs.filter(data_recebimento__month=d["mes"])
        if d["status"] == "VENCIDA":
            qs = qs.vencidas()
        elif d["status"]:
            qs = qs.filter(status=d["status"])
    return qs, form


@login_required
def home(request):
    return redirect("dashboard" if request.user.is_matriz else "painel")


# ---------- Filial ----------

@login_required
def painel(request):
    if request.user.is_matriz:
        return redirect("dashboard")
    ano, mes = _competencia(request)
    filial = request.user.filial
    fechamento = obter_fechamento(filial, ano, mes)
    notificacoes = Notificacao.objects.visiveis_para(request.user)
    return render(request, "core/painel.html", {
        "filial": filial,
        "fechamento": fechamento,
        "ano": ano,
        "mes": mes,
        "do_mes": notificacoes.filter(data_recebimento__year=ano, data_recebimento__month=mes),
        "vencidas": notificacoes.vencidas(),
        "avisos_novos": avisos_service.avisos_nao_lidos(filial),
        "form_justificativa": JustificativaForm(),
        "justificativas": fechamento.justificativas.select_related("autor"),
    })


@login_required
@require_POST
def declarar_sem_notificacoes(request, filial_id, ano, mes):
    filial = get_object_or_404(Filial, pk=filial_id)
    fech.declarar_sem_notificacoes(request.user, filial, ano, mes)
    messages.success(request, "Declaração registrada: sem notificações no mês.")
    return _voltar(request)


@login_required
@require_POST
def desfazer_declaracao(request, filial_id, ano, mes):
    filial = get_object_or_404(Filial, pk=filial_id)
    fech.desfazer_declaracao(request.user, filial, ano, mes)
    messages.info(request, "Declaração desfeita.")
    return _voltar(request)


@login_required
@require_POST
def justificar(request, filial_id, ano, mes):
    filial = get_object_or_404(Filial, pk=filial_id)
    form = JustificativaForm(request.POST)
    if form.is_valid():
        try:
            fech.justificar(request.user, filial, ano, mes, form.cleaned_data["texto"])
            messages.success(request, "Justificativa registrada.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        messages.error(request, "Descreva a justificativa com pelo menos 10 caracteres.")
    return _voltar(request)


# ---------- Notificações ----------

@login_required
def notificacao_lista(request):
    qs, form = _filtrar_notificacoes(request)
    qs = qs.annotate(
        total_avisos=Count("avisos", distinct=True),
        avisos_novos=Count("avisos", filter=Q(avisos__lido_em__isnull=True), distinct=True),
    )
    return render(request, "core/notificacao_lista.html", {
        "notificacoes": qs, "filtro": form, "querystring": request.GET.urlencode(),
    })


@login_required
def notificacao_criar(request):
    form = NotificacaoForm(request.POST or None, request.FILES or None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        fech.registrar_auditoria(request.user, "criar_notificacao", obj)
        messages.success(request, "Notificação registrada.")
        return redirect("notificacao_lista")
    return render(request, "core/notificacao_form.html", {"form": form, "titulo": "Nova notificação"})


def _notificacao_visivel(request, pk):
    return get_object_or_404(Notificacao.objects.visiveis_para(request.user), pk=pk)


@login_required
def notificacao_detalhe(request, pk):
    obj = _notificacao_visivel(request, pk)
    avisos = list(obj.avisos.select_related("autor"))
    # A filial vê os avisos agora; marcamos como lidos só depois de montar a lista (para destacar os novos).
    novos = {a.pk for a in avisos if a.lido_em is None}
    avisos_service.marcar_avisos_lidos(request.user, obj)
    return render(request, "core/notificacao_detalhe.html", {
        "n": obj, "avisos": avisos, "novos": novos,
        "form_status": StatusForm(initial={"status": obj.status}),
        "form_aviso": AvisoForm(initial={"tipo": AvisoNotificacao.Tipo.RESOLVIDA}),
    })


@matriz_required
@require_POST
def notificacao_status(request, pk):
    obj = _notificacao_visivel(request, pk)
    form = StatusForm(request.POST)
    if form.is_valid():
        avisos_service.mudar_status(request.user, obj, form.cleaned_data["status"])
        messages.success(request, "Status atualizado.")
    else:
        messages.error(request, "Status inválido.")
    return redirect("notificacao_detalhe", pk=obj.pk)


@matriz_required
@require_POST
def notificacao_aviso(request, pk):
    obj = _notificacao_visivel(request, pk)
    form = AvisoForm(request.POST)
    if form.is_valid():
        try:
            avisos_service.enviar_aviso(request.user, obj, form.cleaned_data["tipo"], form.cleaned_data["texto"])
            messages.success(request, "Aviso enviado para a filial.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        messages.error(request, "Aviso inválido.")
    return redirect("notificacao_detalhe", pk=obj.pk)


def _somente_filial(request):
    """O conteúdo enviado pela filial só é alterado/excluído pela própria filial."""
    if request.user.is_matriz:
        raise PermissionDenied("A matriz não edita notificações das filiais.")


@login_required
def notificacao_editar(request, pk):
    _somente_filial(request)
    obj = _notificacao_visivel(request, pk)
    form = NotificacaoForm(request.POST or None, request.FILES or None, instance=obj, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        fech.registrar_auditoria(request.user, "editar_notificacao", obj)
        messages.success(request, "Notificação atualizada.")
        return redirect("notificacao_lista")
    return render(request, "core/notificacao_form.html", {"form": form, "titulo": "Editar notificação", "obj": obj})


@login_required
@require_POST
def notificacao_excluir(request, pk):
    _somente_filial(request)
    obj = _notificacao_visivel(request, pk)
    descricao = str(obj)
    obj.delete()
    fech.registrar_auditoria(request.user, "excluir_notificacao", descricao)
    messages.info(request, "Notificação excluída.")
    return redirect("notificacao_lista")


@login_required
def notificacao_anexo(request, pk):
    obj = _notificacao_visivel(request, pk)
    if not obj.anexo:
        raise Http404("Sem anexo.")
    try:
        return FileResponse(obj.anexo.open("rb"), as_attachment=True, filename=obj.anexo.name.rsplit("/", 1)[-1])
    except FileNotFoundError:
        raise Http404("Arquivo não encontrado.")


# ---------- Matriz ----------

@matriz_required
def dashboard(request):
    ano, mes = _competencia(request)
    dados = dash.dados_completos(ano, mes)
    dados["anos"] = range(timezone.localdate().year - 4, timezone.localdate().year + 1)
    dados["meses"] = [(i + 1, nome) for i, nome in enumerate(dash.MESES)]
    return render(request, "core/dashboard.html", dados)


@matriz_required
def nao_enviaram(request):
    ano, mes = _competencia(request)
    linhas = fech.situacao_do_mes(ano, mes)
    return render(request, "core/nao_enviaram.html", {
        "ano": ano, "mes": mes, "linhas": linhas, "form_justificativa": JustificativaForm(),
        "meses": [(i + 1, nome) for i, nome in enumerate(dash.MESES)],
    })


@matriz_required
def filial_lista(request):
    return render(request, "core/filial_lista.html", {"filiais": Filial.objects.all()})


@matriz_required
def filial_form(request, pk=None):
    instance = get_object_or_404(Filial, pk=pk) if pk else None
    form = FilialForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        fech.registrar_auditoria(request.user, "salvar_filial", obj)
        messages.success(request, "Filial salva.")
        return redirect("filial_lista")
    return render(request, "core/form_generico.html", {"form": form, "titulo": "Filial"})


@matriz_required
def usuario_lista(request):
    return render(request, "core/usuario_lista.html", {"usuarios": Usuario.objects.select_related("filial").order_by("username")})


@matriz_required
def usuario_criar(request):
    form = UsuarioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        fech.registrar_auditoria(request.user, "criar_usuario", obj)
        messages.success(request, "Usuário criado.")
        return redirect("usuario_lista")
    return render(request, "core/form_generico.html", {"form": form, "titulo": "Novo usuário"})


# ---------- Exportações ----------

def _resposta(conteudo, nome, tipo):
    resp = HttpResponse(conteudo, content_type=tipo)
    resp["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resp


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@login_required
def exportar_notificacoes(request, formato):
    qs, _ = _filtrar_notificacoes(request)
    if formato == "xlsx":
        return _resposta(exportacao.notificacoes_xlsx(qs), "notificacoes.xlsx", XLSX)
    if formato == "pdf":
        return _resposta(exportacao.notificacoes_pdf(qs), "notificacoes.pdf", "application/pdf")
    raise Http404


@matriz_required
def exportar_dashboard(request, formato):
    ano, mes = _competencia(request)
    dados = dash.dados_completos(ano, mes)
    if formato == "xlsx":
        return _resposta(exportacao.dashboard_xlsx(dados), f"dashboard_{ano}_{mes:02d}.xlsx", XLSX)
    if formato == "pdf":
        return _resposta(exportacao.dashboard_pdf(dados), f"dashboard_{ano}_{mes:02d}.pdf", "application/pdf")
    raise Http404
