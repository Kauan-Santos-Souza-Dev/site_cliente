"""Migration de DADOS: tabela de frete inicial, com valores PROVISÓRIOS (decisão 90).

Os valores reais ainda não existem (pergunta à dona). Estes são EXEMPLOS
por região, todos marcados com is_provisional=True: o admin mostra um aviso
enquanto houver algum provisório. A dona troca pelo admin, sem programador.
"""

from decimal import Decimal

from django.db import migrations

# Região -> (UFs, preço de EXEMPLO).
PROVISIONAL_RATES = {
    'sudeste': (['ES', 'MG', 'RJ', 'SP'], Decimal('19.90')),
    'sul': (['PR', 'RS', 'SC'], Decimal('24.90')),
    'centro_oeste': (['DF', 'GO', 'MS', 'MT'], Decimal('29.90')),
    'nordeste': (['AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE'], Decimal('34.90')),
    'norte': (['AC', 'AM', 'AP', 'PA', 'RO', 'RR', 'TO'], Decimal('39.90')),
}


def create_rates(apps, schema_editor):
    """Cria uma linha por UF (get_or_create: rodar de novo não duplica)."""
    ShippingRate = apps.get_model('pedidos', 'ShippingRate')
    for region, (states, price) in PROVISIONAL_RATES.items():
        for state in states:
            ShippingRate.objects.get_or_create(
                state=state,
                defaults={'region': region, 'price': price, 'is_provisional': True},
            )


def delete_provisional_rates(apps, schema_editor):
    """Desfaz: apaga só as linhas que ainda são provisórias."""
    ShippingRate = apps.get_model('pedidos', 'ShippingRate')
    ShippingRate.objects.filter(is_provisional=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0003_status_antigos_para_novos'),
    ]

    operations = [
        migrations.RunPython(create_rates, delete_provisional_rates),
    ]
