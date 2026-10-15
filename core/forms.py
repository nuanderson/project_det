from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import AvisoNotificacao, Filial, Notificacao, Usuario


class NotificacaoForm(forms.ModelForm):
    class Meta:
        model = Notificacao
        fields = ["filial", "numero_det", "assunto", "data_recebimento", "prazo_resposta", "status", "anexo", "observacao"]
        widgets = {
            "data_recebimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "prazo_resposta": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        if usuario.is_matriz:
            self.fields["filial"].queryset = Filial.objects.filter(ativa=True)
        else:
            # Filial não escolhe a filial: é sempre a dela.
            del self.fields["filial"]

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not self.usuario.is_matriz:
            obj.filial_id = self.usuario.filial_id
        if not obj.pk:
            obj.criado_por = self.usuario
        if commit:
            obj.save()
        return obj


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
    filial = forms.ModelChoiceField(Filial.objects.all(), required=False, empty_label="Todas as filiais")
    ano = forms.IntegerField(required=False, min_value=2000, max_value=2100)
    mes = forms.IntegerField(required=False, min_value=1, max_value=12)
    status = forms.ChoiceField(
        required=False,
        choices=[("", "Todos os status")] + list(Notificacao.Status.choices) + [("VENCIDA", "Vencida")],
    )
