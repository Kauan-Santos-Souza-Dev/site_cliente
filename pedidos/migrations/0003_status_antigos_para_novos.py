"""Migration de DADOS: troca os status da v1 pelos da v2 (decisão 87).

RunPython roda uma função Python durante o migrate. Ela recebe `apps`, um
"retrato" dos models COMO ELES ERAM nesta migration (e não o models.py de
hoje, que pode mudar no futuro). Por isso usamos apps.get_model() em vez de
importar Order.

Mapa:
    novo        -> aguardando_pagamento  (sem prazo: expires_at fica vazio,
                                          então NUNCA expira sozinho; a dona
                                          decide no admin)
    confirmado  -> pago                  (na v1, "confirmado" = a dona
                                          combinou e recebeu pelo WhatsApp)
    enviado, cancelado -> iguais

update() muda tudo direto no banco, sem chamar Order.save(): nenhuma regra
de transição nem de estoque é disparada (o estoque desses pedidos já está
certo).
"""

from django.db import migrations

FORWARD = {'novo': 'aguardando_pagamento', 'confirmado': 'pago'}
BACKWARD = {new: old for old, new in FORWARD.items()}


def to_new_status(apps, schema_editor):
    """v1 -> v2."""
    Order = apps.get_model('pedidos', 'Order')
    for old, new in FORWARD.items():
        Order.objects.filter(status=old).update(status=new)


def to_old_status(apps, schema_editor):
    """v2 -> v1 (para poder desfazer com `migrate pedidos 0002`).

    Status que não existiam na v1 viram "cancelado" (expirado, estornado):
    o estoque deles já foi devolvido, que é o que "cancelado" significava.
    """
    Order = apps.get_model('pedidos', 'Order')
    for new, old in BACKWARD.items():
        Order.objects.filter(status=new).update(status=old)
    Order.objects.filter(status__in=['expirado', 'estornado']).update(status='cancelado')


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0002_pedido_ligado_a_conta_e_status'),
    ]

    operations = [
        migrations.RunPython(to_new_status, to_old_status),
    ]
