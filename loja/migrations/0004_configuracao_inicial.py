"""Migration de DADOS: cria a linha única de configuração da loja (decisão 89).

Frete grátis a partir de R$ 299,00 é um valor de EXEMPLO (PROVISÓRIO), à
espera da resposta da dona. A reserva de 30 minutos vem da decisão 58.
"""

from decimal import Decimal

from django.db import migrations


def create_settings(apps, schema_editor):
    """Cria a configuração com id=1 (se ainda não existir)."""
    StoreSettings = apps.get_model('loja', 'StoreSettings')
    StoreSettings.objects.get_or_create(
        pk=1,
        defaults={
            'reservation_minutes': 30,
            'free_shipping_threshold': Decimal('299.00'),
            'free_shipping_is_provisional': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('loja', '0003_configuracao_da_loja'),
    ]

    operations = [
        # noop na volta: a tabela inteira é apagada ao desfazer a 0003.
        migrations.RunPython(create_settings, migrations.RunPython.noop),
    ]
