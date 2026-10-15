import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Filial, Notificacao, Usuario
from core.services.fechamento import situacao_do_mes


def _emails_matriz():
    return list(
        Usuario.objects.filter(perfil=Usuario.Perfil.MATRIZ, is_active=True).exclude(email="").values_list("email", flat=True)
    )


def _emails_filial(filial):
    destinos = {filial.email} if filial.email else set()
    destinos |= set(filial.usuarios.filter(is_active=True).exclude(email="").values_list("email", flat=True))
    return sorted(destinos)


class Command(BaseCommand):
    help = "Envia lembretes de fechamento mensal pendente e avisos de prazo. Agende diariamente."

    def add_arguments(self, parser):
        parser.add_argument("--forcar-lembrete", action="store_true", help="Envia o lembrete mensal mesmo fora do dia configurado.")

    def handle(self, *args, **opts):
        hoje = timezone.localdate()
        enviados = 0
        if opts["forcar_lembrete"] or hoje.day == settings.ALERTA_DIA_LEMBRETE_MENSAL:
            enviados += self.lembrete_mensal(hoje)
        enviados += self.avisos_de_prazo(hoje)
        enviados += self.resumo_vencidas(hoje)
        self.stdout.write(self.style.SUCCESS(f"{enviados} e-mail(s) enviado(s)."))

    def lembrete_mensal(self, hoje):
        # Competência anterior: o mês que acabou de fechar.
        ref = (hoje.replace(day=1) - datetime.timedelta(days=1))
        enviados = 0
        pendentes = [l for l in situacao_do_mes(ref.year, ref.month) if l["situacao"] == "PENDENTE"]
        for linha in pendentes:
            filial = linha["filial"]
            destinos = _emails_filial(filial)
            if destinos:
                send_mail(
                    f"Controle DET: informe as notificações de {ref.month:02d}/{ref.year}",
                    f"A filial {filial.nome} ainda não registrou notificações nem declarou 'sem notificações' "
                    f"para {ref.month:02d}/{ref.year}. Acesse o sistema e regularize ou justifique.",
                    settings.DEFAULT_FROM_EMAIL, destinos,
                )
                enviados += 1
        matriz = _emails_matriz()
        if pendentes and matriz:
            lista = "\n".join(f"- {l['filial'].nome}" for l in pendentes)
            send_mail(
                f"Controle DET: filiais pendentes em {ref.month:02d}/{ref.year}",
                f"Filiais sem informação no mês:\n{lista}", settings.DEFAULT_FROM_EMAIL, matriz,
            )
            enviados += 1
        return enviados

    def avisos_de_prazo(self, hoje):
        enviados = 0
        for dias in settings.ALERTA_DIAS_ANTES_PRAZO:
            alvo = hoje + datetime.timedelta(days=dias)
            for filial in Filial.objects.filter(ativa=True):
                notificacoes = Notificacao.objects.abertas().filter(filial=filial, prazo_resposta=alvo)
                destinos = _emails_filial(filial)
                if notificacoes and destinos:
                    lista = "\n".join(f"- {n.numero_det}: {n.assunto}" for n in notificacoes)
                    send_mail(
                        f"Controle DET: prazo em {dias} dia(s)",
                        f"Notificações da filial {filial.nome} com prazo em {alvo:%d/%m/%Y}:\n{lista}",
                        settings.DEFAULT_FROM_EMAIL, destinos,
                    )
                    enviados += 1
        return enviados

    def resumo_vencidas(self, hoje):
        vencidas = Notificacao.objects.vencidas(hoje).select_related("filial")
        matriz = _emails_matriz()
        if not vencidas.exists() or not matriz:
            return 0
        lista = "\n".join(f"- {n.filial.nome}: {n.numero_det} (prazo {n.prazo_resposta:%d/%m/%Y})" for n in vencidas)
        send_mail("Controle DET: notificações vencidas", lista, settings.DEFAULT_FROM_EMAIL, matriz)
        return 1
