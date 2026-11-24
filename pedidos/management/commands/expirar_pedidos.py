"""Comando `python manage.py expirar_pedidos` (decisão 88).

Expira os pedidos aguardando pagamento cujo prazo de reserva venceu e
devolve as peças ao estoque. Pode rodar quantas vezes quiser: um pedido
já expirado não é tocado de novo.

Feito para um AGENDADOR chamar sozinho, por exemplo a cada 5 minutos. A
hospedagem ainda não foi escolhida; qualquer um serve:
- Linux (cron):       */5 * * * *  cd /caminho && .venv/bin/python manage.py expirar_pedidos
- Windows:            Agendador de Tarefas, repetindo a cada 5 minutos
- Hospedagem:         o "scheduler"/"cron job" do painel

Mesmo sem agendador, as páginas de produto, carrinho, checkout e Meus
pedidos expiram os vencidos ao serem abertas (rede de segurança).

Use --dry-run para só CONTAR, sem mudar nada.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from pedidos.reservations import expire_overdue_orders, overdue_orders


class Command(BaseCommand):
    """Expira pedidos não pagos com a reserva vencida."""

    help = 'Expira pedidos não pagos cujo prazo de reserva venceu e devolve o estoque.'

    def add_arguments(self, parser):
        """Opção --dry-run: mostra quantos seriam expirados, sem alterar o banco."""
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Só conta os pedidos; não altera nada.',
        )

    def handle(self, *args, **options):
        """Roda a expiração e mostra só a QUANTIDADE (nunca dados das clientes)."""
        now = timezone.now()
        if options['dry_run']:
            count = overdue_orders(now).count()
            self.stdout.write(f'Pedidos que seriam expirados: {count}')
            self.stdout.write(self.style.SUCCESS('Simulação concluída. Nada foi alterado.'))
            return
        count = expire_overdue_orders(now)
        self.stdout.write(self.style.SUCCESS(f'Pedidos expirados (estoque devolvido): {count}'))
