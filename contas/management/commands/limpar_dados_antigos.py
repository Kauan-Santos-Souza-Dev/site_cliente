"""Comando `python manage.py limpar_dados_antigos` (decisão 79).

Aplica os prazos de retenção de contas/legal.py:
1. anonimiza nome, telefone e endereço dos pedidos com mais de 5 anos;
2. apaga contas que nunca confirmaram o e-mail, criadas há mais de 30 dias;
3. apaga tentativas de login (django-axes) com mais de 30 dias;
4. apaga as sessões vencidas (comando `clearsessions` do Django).

Use --dry-run para só CONTAR, sem mudar nada.

HOJE O COMANDO É MANUAL. Em produção ele precisa rodar sozinho (por
exemplo, uma vez por dia), e o jeito de agendar depende da hospedagem,
que ainda não foi escolhida. O agendamento é pré-requisito para publicar
a loja (decisão 69).
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from contas.privacy import (
    anonymize_old_orders,
    delete_old_login_attempts,
    delete_old_unverified_accounts,
)


class Command(BaseCommand):
    """Aplica os prazos de retenção de dados pessoais."""

    help = 'Anonimiza ou apaga dados pessoais que passaram do prazo de retenção.'

    def add_arguments(self, parser):
        """Opção --dry-run: mostra o que seria feito, sem alterar o banco."""
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Só conta os registros; não altera nada.',
        )

    def handle(self, *args, **options):
        """Roda cada limpeza e mostra quantos registros foram afetados (só números)."""
        dry_run = options['dry_run']
        now = timezone.now()
        verb = 'seriam' if dry_run else 'foram'

        # A saída mostra só QUANTIDADES, nunca nomes ou e-mails: o terminal
        # (ou o log do agendador, em produção) não pode guardar dado pessoal.
        orders = anonymize_old_orders(now, dry_run=dry_run)
        self.stdout.write(f'Pedidos com mais de 5 anos que {verb} anonimizados: {orders}')

        accounts = delete_old_unverified_accounts(now, dry_run=dry_run)
        self.stdout.write(f'Contas nunca verificadas que {verb} apagadas: {accounts}')

        attempts = delete_old_login_attempts(now, dry_run=dry_run)
        self.stdout.write(f'Registros de login antigos que {verb} apagados: {attempts}')

        if dry_run:
            self.stdout.write('Sessões vencidas: seriam apagadas pelo clearsessions.')
        else:
            call_command('clearsessions')
            self.stdout.write('Sessões vencidas apagadas.')

        self.stdout.write(self.style.SUCCESS('Pronto.' if not dry_run else 'Simulação concluída. Nada foi alterado.'))
