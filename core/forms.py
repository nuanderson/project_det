import re

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import AtualizacaoNotificacao, AvisoNotificacao, Filial, Notificacao, Usuario
from .services.historico import registrar_atualizacao
from .validators import validar_anexo


class NotificacaoForm(forms.ModelForm):
    class Meta:
        model = Notificacao
        fields = [
            "filial", "tipo", "numero_det", "assunto", "data_recebimento", "prazo_resposta", "status",
            "numero_processo", "inscricao", "codigo_acesso", "anexo", "observacao",
        ]
        widgets = {
            "data_recebimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "prazo_resposta": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    atualizacao = forms.CharField(
        label="Histórico: registrar atualização", required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Cada atualização fica registrada com data e autor e não pode ser editada nem apagada.",
    )

    def __init__(self, *args, usuario, pdf_importado=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.pdf_importado = pdf_importado
        if pdf_importado:
            self.fields["anexo"].required = False
            self.fields["anexo"].help_text = (
                f"O PDF importado ({pdf_importado}) será anexado automaticamente. "
                "Escolha outro arquivo apenas se quiser substituí-lo."
            )
        self.fields["tipo"].required = False  # omitido = Notificação (padrão do modelo)
        if usuario.is_matriz:
            self.fields["filial"].queryset = Filial.objects.filter(ativa=True)
        else:
            # Filial não escolhe a filial: é sempre a dela.
            del self.fields["filial"]

    def clean_numero_processo(self):
        return re.sub(r"\D", "", self.cleaned_data["numero_processo"])

    def clean_inscricao(self):
        valor = re.sub(r"\D", "", self.cleaned_data["inscricao"])
        if valor and len(valor) != 14:
            raise forms.ValidationError("Informe o CNPJ com 14 dígitos.")
        return valor

    def clean_codigo_acesso(self):
        valor = self.cleaned_data["codigo_acesso"].strip().upper()
        if valor and not re.fullmatch(r"[A-Z0-9]{4,20}", valor):
            raise forms.ValidationError("Use apenas letras e números.")
        return valor

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not self.usuario.is_matriz:
            obj.filial_id = self.usuario.filial_id
        novo = not obj.pk
        status_antes = None if novo else Notificacao.objects.filter(pk=obj.pk).values_list("status", flat=True).first()
        if novo:
            obj.criado_por = self.usuario
        if commit:
            obj.save()
            self._registrar_historico(obj, novo, status_antes)
        return obj

    def _registrar_historico(self, obj, novo, status_antes):
        Origem = AtualizacaoNotificacao.Origem
        if novo and self.pdf_importado:
            registrar_atualizacao(obj, self.usuario, f"Notificação importada do PDF «{self.pdf_importado}» e anexada.", Origem.IMPORTACAO)
        if status_antes and status_antes != obj.status:
            rotulos = dict(Notificacao.Status.choices)
            registrar_atualizacao(
                obj, self.usuario, f"Status alterado de {rotulos[status_antes]} para {rotulos[obj.status]}.", Origem.STATUS
            )
        registrar_atualizacao(obj, self.usuario, self.cleaned_data.get("atualizacao"), Origem.MANUAL)


class ImportarPDFForm(forms.Form):
    pdf = forms.FileField(label="PDF exportado do DET", validators=[validar_anexo])

    def clean_pdf(self):
        arquivo = self.cleaned_data["pdf"]
        if not arquivo.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Envie um arquivo PDF.")
        if arquivo.read(5) != b"%PDF-":
            raise forms.ValidationError("O arquivo não parece ser um PDF válido.")
        arquivo.seek(0)
        return arquivo


class JustificativaForm(forms.Form):
    texto = forms.CharField(
        label="Justificativa do não envio",
        min_length=10,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class StatusForm(forms.Form):
    status = forms.ChoiceField(label="Status", choices=Notificacao.Status.choices)


class AvisoForm(forms.Form):
    tipo = forms.ChoiceField(label="Tipo de aviso", choices=AvisoNotificacao.Tipo.choices)
    texto = forms.CharField(
        label="Mensagem para a filial", required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Obrigatória para problema no envio (ex.: anexo não veio).",
    )


class FilialForm(forms.ModelForm):
    class Meta:
        model = Filial
        fields = ["nome", "cnpj", "cidade", "uf", "email", "ativa"]


class UsuarioForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ["username", "first_name", "email", "perfil", "filial"]

    def clean(self):
        cleaned = super().clean()
        perfil, filial = cleaned.get("perfil"), cleaned.get("filial")
        if perfil == Usuario.Perfil.FILIAL and not filial:
            self.add_error("filial", "Usuário de filial precisa de uma filial.")
        if perfil == Usuario.Perfil.MATRIZ and filial:
            self.add_error("filial", "Usuário da matriz não deve ter filial.")
        return cleaned


class FiltroNotificacaoForm(forms.Form):
    filial = forms.ModelChoiceField(
        Filial.objects.all(), required=False, empty_label="Todas as filiais",
        widget=forms.Select(attrs={"aria-label": "Filial"}),
    )
    ano = forms.IntegerField(
        required=False, min_value=2000, max_value=2100,
        widget=forms.NumberInput(attrs={"placeholder": "Ano", "aria-label": "Ano"}),
    )
    mes = forms.IntegerField(
        required=False, min_value=1, max_value=12,
        widget=forms.NumberInput(attrs={"placeholder": "Mês (1-12)", "aria-label": "Mês"}),
    )
    prazo = forms.ChoiceField(required=False, choices=[("", ""), ("7", "Prazo nos próximos 7 dias")], widget=forms.HiddenInput)
    status = forms.ChoiceField(
        required=False,
        choices=[("", "Todos os status")] + list(Notificacao.Status.choices) + [("VENCIDA", "Vencida")],
    )
