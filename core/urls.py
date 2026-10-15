from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("painel/", views.painel, name="painel"),
    path("fechamento/<int:filial_id>/<int:ano>/<int:mes>/sem-notificacoes/", views.declarar_sem_notificacoes, name="declarar_sem"),
    path("fechamento/<int:filial_id>/<int:ano>/<int:mes>/desfazer/", views.desfazer_declaracao, name="desfazer_declaracao"),
    path("fechamento/<int:filial_id>/<int:ano>/<int:mes>/justificar/", views.justificar, name="justificar"),
    path("notificacoes/", views.notificacao_lista, name="notificacao_lista"),
    path("notificacoes/nova/", views.notificacao_criar, name="notificacao_criar"),
    path("notificacoes/<int:pk>/editar/", views.notificacao_editar, name="notificacao_editar"),
    path("notificacoes/<int:pk>/excluir/", views.notificacao_excluir, name="notificacao_excluir"),
    path("notificacoes/<int:pk>/anexo/", views.notificacao_anexo, name="notificacao_anexo"),
    path("notificacoes/exportar/<str:formato>/", views.exportar_notificacoes, name="exportar_notificacoes"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/exportar/<str:formato>/", views.exportar_dashboard, name="exportar_dashboard"),
    path("nao-enviaram/", views.nao_enviaram, name="nao_enviaram"),
    path("filiais/", views.filial_lista, name="filial_lista"),
    path("filiais/nova/", views.filial_form, name="filial_nova"),
    path("filiais/<int:pk>/", views.filial_form, name="filial_editar"),
    path("usuarios/", views.usuario_lista, name="usuario_lista"),
    path("usuarios/novo/", views.usuario_criar, name="usuario_criar"),
]
