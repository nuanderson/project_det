from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AvisoNotificacao, FechamentoMensal, Filial, JustificativaHistorico, LogAuditoria, Notificacao, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Controle DET", {"fields": ("perfil", "filial")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Controle DET", {"fields": ("perfil", "filial")}),)
    list_display = ("username", "perfil", "filial", "is_active")


@admin.register(Filial)
class FilialAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj", "cidade", "uf", "ativa")
    search_fields = ("nome", "cnpj")


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ("numero_det", "filial", "data_recebimento", "prazo_resposta", "status")
    list_filter = ("filial", "status")


@admin.register(FechamentoMensal)
class FechamentoAdmin(admin.ModelAdmin):
    list_display = ("filial", "ano", "mes", "situacao")
    list_filter = ("situacao", "ano", "mes")


class SomenteLeitura(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JustificativaHistorico)
class JustificativaAdmin(SomenteLeitura):
    list_display = ("fechamento", "autor", "criado_em")


@admin.register(LogAuditoria)
class LogAdmin(SomenteLeitura):
    list_display = ("criado_em", "usuario", "acao", "objeto")


@admin.register(AvisoNotificacao)
class AvisoAdmin(SomenteLeitura):
    list_display = ("notificacao", "tipo", "autor", "criado_em", "lido_em")
