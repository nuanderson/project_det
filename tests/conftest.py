import datetime

import pytest
from django.utils import timezone

from core.models import Filial, Notificacao, Usuario


@pytest.fixture(autouse=True)
def media_temporaria(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "anexos"


@pytest.fixture
def filial_a(db):
    return Filial.objects.create(nome="Filial A", cnpj="11.111.111/0001-11")


@pytest.fixture
def filial_b(db):
    return Filial.objects.create(nome="Filial B", cnpj="22.222.222/0001-22")


@pytest.fixture
def matriz(db):
    return Usuario.objects.create_user("matriz", password="x-senha-forte-1", perfil="MATRIZ")


@pytest.fixture
def user_a(filial_a):
    return Usuario.objects.create_user("ua", password="x-senha-forte-1", perfil="FILIAL", filial=filial_a)


@pytest.fixture
def user_b(filial_b):
    return Usuario.objects.create_user("ub", password="x-senha-forte-1", perfil="FILIAL", filial=filial_b)


@pytest.fixture
def criar_notificacao():
    def _criar(filial, usuario, data=None, prazo=None, status="PENDENTE", numero="N1"):
        data = data or timezone.localdate()
        return Notificacao.objects.create(
            filial=filial, numero_det=numero, assunto="Assunto", data_recebimento=data,
            prazo_resposta=prazo, status=status, criado_por=usuario,
        )
    return _criar


@pytest.fixture
def hoje():
    return timezone.localdate()


@pytest.fixture
def dias():
    return datetime.timedelta
