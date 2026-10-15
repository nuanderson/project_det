from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Notificacao, obter_fechamento


def _recalcular(filial_id, data):
    from .models import Filial

    filial = Filial.objects.get(pk=filial_id)
    obter_fechamento(filial, data.year, data.month).recalcular()


@receiver(pre_save, sender=Notificacao)
def guardar_competencia_anterior(sender, instance, **kwargs):
    instance._competencia_anterior = None
    if instance.pk:
        anterior = Notificacao.objects.filter(pk=instance.pk).values_list("filial_id", "data_recebimento").first()
        if anterior:
            instance._competencia_anterior = anterior


@receiver(post_save, sender=Notificacao)
def recalcular_apos_salvar(sender, instance, **kwargs):
    _recalcular(instance.filial_id, instance.data_recebimento)
    anterior = getattr(instance, "_competencia_anterior", None)
    if anterior and anterior != (instance.filial_id, instance.data_recebimento):
        _recalcular(*anterior)


@receiver(post_delete, sender=Notificacao)
def recalcular_apos_excluir(sender, instance, **kwargs):
    _recalcular(instance.filial_id, instance.data_recebimento)
