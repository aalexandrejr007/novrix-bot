"""Cria o usuário do painel a partir de ADMIN_USER e ADMIN_PASSWORD (só se ainda não existir).

Assim não é preciso abrir o Shell do Render, que só existe nos planos pagos.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria o administrador do painel a partir das variáveis ADMIN_USER e ADMIN_PASSWORD."

    def handle(self, *args, **opts):
        usuario = os.environ.get("ADMIN_USER", "").strip()
        senha = os.environ.get("ADMIN_PASSWORD", "")
        if not usuario or not senha:
            self.stdout.write("ADMIN_USER/ADMIN_PASSWORD não definidos: nenhum administrador criado.")
            return
        User = get_user_model()
        if User.objects.filter(username=usuario).exists():
            self.stdout.write(f"Administrador '{usuario}' já existe.")
            return
        User.objects.create_superuser(username=usuario, email="", password=senha)
        self.stdout.write(self.style.SUCCESS(f"Administrador '{usuario}' criado."))
