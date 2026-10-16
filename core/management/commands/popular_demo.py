import datetime
import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Filial, Notificacao, Usuario


class Command(BaseCommand):
    help = (
        "Cria dados de demonstração (matriz, 3 filiais e notificações). Só para teste: "
        "roda com DET_DEBUG=True ou, num link de teste online, com DET_PERMITIR_DEMO=True e DET_DEMO_SENHA."
    )

    def handle(self, *args, **opts):
        # Cria usuários com senha conhecida: nunca pode rodar num servidor real por acidente.
        online = not settings.DEBUG
        if online and not settings.PERMITIR_DEMO:
            raise CommandError("popular_demo só roda com DET_DEBUG=True ou DET_PERMITIR_DEMO=True (ambiente de teste).")
        if online and len(settings.DEMO_SENHA) < 10:
            raise CommandError("Defina DET_DEMO_SENHA com pelo menos 10 caracteres para a demonstração online.")

        def senha(padrao):
            # Local: senhas fixas de teste. Online: uma senha vinda do ambiente, nunca do código.
            return settings.DEMO_SENHA if online else padrao

        random.seed(1)
        hoje = timezone.localdate()
        matriz, criado = Usuario.objects.get_or_create(
            username="matriz",
            defaults={
                "perfil": "MATRIZ", "email": "matriz@exemplo.local",
                # Sem acesso ao /admin/ no link público.
                "is_staff": not online, "is_superuser": not online,
            },
        )
        if criado:
            matriz.set_password(senha("matriz-demo-123"))
            matriz.save()
        for i, nome in enumerate(["Filial Norte", "Filial Sul", "Filial Centro"], start=1):
            filial, _ = Filial.objects.get_or_create(
                nome=nome, defaults={"cnpj": f"00.000.000/000{i}-0{i}", "cidade": nome.split()[1], "uf": "SP"}
            )
            user, criado = Usuario.objects.get_or_create(
                username=f"filial{i}", defaults={"perfil": "FILIAL", "filial": filial, "email": f"filial{i}@exemplo.local"}
            )
            if criado:
                user.set_password(senha(f"filial{i}-demo-123"))
                user.save()
            if filial.notificacoes.exists():
                continue  # já populada: não duplica ao rodar de novo
            # Filial Centro (i=3) fica sem registros no mês atual para exercitar o "não enviou".
            for n in range(random.randint(2, 5)):
                if i == 3 and n > 0:
                    break
                recebido = hoje - datetime.timedelta(days=random.randint(0, 150))
                if i == 3 and recebido.month == hoje.month and recebido.year == hoje.year:
                    recebido -= datetime.timedelta(days=35)
                Notificacao.objects.create(
                    filial=filial, numero_det=f"DET-{i}{n:03d}", assunto="Solicitação de documentos",
                    data_recebimento=recebido, prazo_resposta=recebido + datetime.timedelta(days=random.choice([5, 10, 15])),
                    status=random.choice(list(Notificacao.Status.values)), criado_por=user,
                )
        quais = "a senha definida em DET_DEMO_SENHA" if online else "senhas *-demo-123"
        self.stdout.write(self.style.SUCCESS(f"Dados demo prontos. Logins: matriz / filial1..3 ({quais})."))
