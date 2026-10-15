import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .validators import validar_anexo


class Filial(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)
    cidade = models.CharField(max_length=80, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    email = models.EmailField("E-mail para alertas", blank=True)
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name_plural = "filiais"

    def __str__(self):
        return self.nome


class UsuarioManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # Administrador é sempre da matriz (sem filial), para já acessar dashboard e cadastros.
        extra_fields.setdefault("perfil", Usuario.Perfil.MATRIZ)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    objects = UsuarioManager()

    class Perfil(models.TextChoices):
        MATRIZ = "MATRIZ", "Matriz"
        FILIAL = "FILIAL", "Filial"

    perfil = models.CharField(max_length=10, choices=Perfil.choices, default=Perfil.FILIAL)
    filial = models.ForeignKey(Filial, null=True, blank=True, on_delete=models.PROTECT, related_name="usuarios")

    @property
    def is_matriz(self):
        return self.perfil == self.Perfil.MATRIZ

    def clean(self):
        super().clean()
        if self.perfil == self.Perfil.FILIAL and not self.filial_id:
            raise ValidationError({"filial": "Usuário de filial precisa estar vinculado a uma filial."})
        if self.perfil == self.Perfil.MATRIZ and self.filial_id:
            raise ValidationError({"filial": "Usuário da matriz não deve ter filial."})


class NotificacaoQuerySet(models.QuerySet):
    def da_filial(self, filial):
        return self.filter(filial=filial)

    def visiveis_para(self, usuario):
        """Ponto único de escopo: filial só enxerga a própria; matriz enxerga tudo."""
        if usuario.is_matriz:
            return self
        return self.filter(filial_id=usuario.filial_id)

    def abertas(self):
        return self.exclude(status=Notificacao.Status.RESPONDIDA)

    def vencidas(self, hoje=None):
        hoje = hoje or timezone.localdate()
        return self.abertas().filter(prazo_resposta__lt=hoje)


def caminho_anexo(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"filial_{instance.filial_id}/{instance.data_recebimento:%Y/%m}/{uuid.uuid4().hex}.{ext}"


class Notificacao(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        RESPONDIDA = "RESPONDIDA", "Respondida"

    filial = models.ForeignKey(Filial, on_delete=models.PROTECT, related_name="notificacoes")
    numero_det = models.CharField("Nº / identificação no DET", max_length=60)
    assunto = models.CharField(max_length=200)
    data_recebimento = models.DateField("Data de recebimento")
    prazo_resposta = models.DateField("Prazo de resposta", null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDENTE)
    anexo = models.FileField(upload_to=caminho_anexo, blank=True, validators=[validar_anexo])
    observacao = models.TextField("Observação", blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = NotificacaoQuerySet.as_manager()

    class Meta:
        ordering = ["-data_recebimento", "-id"]
        verbose_name = "notificação"
        verbose_name_plural = "notificações"

    def __str__(self):
        return f"{self.numero_det} - {self.filial}"

    @property
    def vencida(self):
        return bool(
            self.prazo_resposta
            and self.status != self.Status.RESPONDIDA
            and self.prazo_resposta < timezone.localdate()
        )

    @property
    def status_exibicao(self):
        """VENCIDA é derivada do prazo, não armazenada, para nunca ficar desatualizada."""
        return "Vencida" if self.vencida else self.get_status_display()

    def clean(self):
        super().clean()
        if self.prazo_resposta and self.data_recebimento and self.prazo_resposta < self.data_recebimento:
            raise ValidationError({"prazo_resposta": "O prazo não pode ser anterior à data de recebimento."})


class AvisoNotificacao(models.Model):
    """Aviso da matriz para a filial sobre uma notificação (resolvida ou com problema). Só inserção."""

    class Tipo(models.TextChoices):
        RESOLVIDA = "RESOLVIDA", "Resolvida"
        PROBLEMA = "PROBLEMA", "Problema no envio"

    notificacao = models.ForeignKey(Notificacao, on_delete=models.CASCADE, related_name="avisos")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    texto = models.TextField(blank=True)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    lido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        verbose_name = "aviso da matriz"
        verbose_name_plural = "avisos da matriz"

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.notificacao}"

    def clean(self):
        super().clean()
        if self.tipo == self.Tipo.PROBLEMA and len((self.texto or "").strip()) < 5:
            raise ValidationError({"texto": "Descreva o problema para a filial (ex.: anexo não veio)."})


class FechamentoMensal(models.Model):
    class Situacao(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        COM_NOTIFICACOES = "COM_NOTIFICACOES", "Com notificações"
        SEM_NOTIFICACOES = "SEM_NOTIFICACOES", "Sem notificações"
        JUSTIFICADO = "JUSTIFICADO", "Justificado"

    filial = models.ForeignKey(Filial, on_delete=models.CASCADE, related_name="fechamentos")
    ano = models.PositiveSmallIntegerField()
    mes = models.PositiveSmallIntegerField()
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.PENDENTE)
    declarou_sem_notificacoes = models.BooleanField(default=False)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ano", "-mes", "filial__nome"]
        constraints = [models.UniqueConstraint(fields=["filial", "ano", "mes"], name="fechamento_unico")]

    def __str__(self):
        return f"{self.filial} {self.mes:02d}/{self.ano}"

    def recalcular(self):
        """Situação derivada dos fatos: notificações do mês > declaração > justificativa > pendente."""
        tem_notificacao = Notificacao.objects.filter(
            filial_id=self.filial_id, data_recebimento__year=self.ano, data_recebimento__month=self.mes
        ).exists()
        if tem_notificacao:
            nova = self.Situacao.COM_NOTIFICACOES
        elif self.declarou_sem_notificacoes:
            nova = self.Situacao.SEM_NOTIFICACOES
        elif self.justificativas.exists():
            nova = self.Situacao.JUSTIFICADO
        else:
            nova = self.Situacao.PENDENTE
        if nova != self.situacao:
            self.situacao = nova
            self.save(update_fields=["situacao", "atualizado_em"])
        return nova


class JustificativaHistorico(models.Model):
    """Somente inserção: cada justificativa fica registrada, sem edição nem exclusão."""

    fechamento = models.ForeignKey(FechamentoMensal, on_delete=models.CASCADE, related_name="justificativas")
    texto = models.TextField()
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em", "-id"]

    def __str__(self):
        return f"Justificativa de {self.fechamento}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Justificativas não podem ser editadas.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Justificativas não podem ser excluídas.")


class LogAuditoria(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    acao = models.CharField(max_length=30)
    objeto = models.CharField(max_length=200)
    detalhe = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        verbose_name = "log de auditoria"
        verbose_name_plural = "logs de auditoria"


def competencia_atual(hoje=None):
    hoje = hoje or timezone.localdate()
    return hoje.year, hoje.month


def obter_fechamento(filial, ano, mes):
    fechamento, _ = FechamentoMensal.objects.get_or_create(filial=filial, ano=ano, mes=mes)
    return fechamento
