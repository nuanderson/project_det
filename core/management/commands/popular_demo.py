import datetime
import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Filial, Notificacao, Usuario


class Command(BaseCommand):
    help = "Cria dados de demonstração (matriz, 3 filiais e notificações). Só para desenvolvimento."

    def handle(self, *args, **opts):
        # Cria usuários com senhas conhecidas: nunca pode rodar num servidor real.
        if not settings.DEBUG:
            raise CommandError("popular_demo só roda com DET_DEBUG=True (ambiente de teste).")
        random.seed(1)
        hoje = timezone.localdate()
        matriz, criado = Usuario.objects.get_or_create(
            username="matriz", defaults={"perfil": "MATRIZ", "email": "matriz@exemplo.local", "is_staff": True, "is_superuser": True}
        )
        if criado:
            matriz.set_password("matriz-demo-123")
            matriz.save()
        for i, nome in enumerate(["Filial Norte", "Filial Sul", "Filial Centro"], start=1):
            filial, _ = Filial.objects.get_or_create(
                nome=nome, defaults={"cnpj": f"00.000.000/000{i}-0{i}", "cidade": nome.split()[1], "uf": "SP"}
            )
            user, criado = Usuario.objects.get_or_create(
                username=f"filial{i}", defaults={"perfil": "FILIAL", "filial": filial, "email": f"filial{i}@exemplo.local"}
            )
            if criado:
                user.set_password(f"filial{i}-demo-123")
                user.save()
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
        self.stdout.write(self.style.SUCCESS("Dados demo criados. Logins: matriz / filial1..3 (senhas *-demo-123)."))
