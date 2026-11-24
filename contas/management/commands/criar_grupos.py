"""Cria (ou atualiza) o grupo de permissões "Loja" do admin (decisão 76).

Como usar (depois do migrate):
    python manage.py criar_grupos

O que é um grupo?
No Django, cada model ganha as permissões "add", "change", "delete" e
"view". Um grupo junta várias permissões; uma conta do admin colocada no
grupo recebe todas elas. A superusuária tem tudo, sempre.

Por que um comando e não uma migration?
As permissões são criadas pelo Django DEPOIS das migrations (sinal
post_migrate). Numa migration de dados elas podem ainda não existir. O
comando roda depois e pode ser repetido sem duplicar nada.
"""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

GROUP_NAME = 'Loja'

# (app, model): ações permitidas. Fica DE FORA de propósito: contas de
# clientes (contas.user), grupos e permissões, dispositivos de 2FA e
# registros do axes. Assim, a conta do dia a dia cuida da loja, mas não vê a
# lista de clientes nem mexe na segurança do painel.
GROUP_PERMISSIONS = {
    ('loja', 'category'): ['view'],  # categorias são fixas (decisão 9)
    ('loja', 'product'): ['add', 'change', 'delete', 'view'],
    ('loja', 'productvariant'): ['add', 'change', 'delete', 'view'],
    ('loja', 'productimage'): ['add', 'change', 'delete', 'view'],
    # Configuração da loja: uma linha só, que não se cria nem se apaga (decisão 89).
    ('loja', 'storesettings'): ['change', 'view'],
    # Pedido: o status muda só pelas ações do admin, e o admin limita o que
    # pode ser apagado (decisões 46 e 87).
    ('pedidos', 'order'): ['change', 'delete', 'view'],
    ('pedidos', 'orderitem'): ['view'],
    # Tabela de frete por UF (decisão 90).
    ('pedidos', 'shippingrate'): ['add', 'change', 'delete', 'view'],
}


def get_group_permissions():
    """Busca no banco os objetos Permission da lista acima."""
    permissions = []
    for (app_label, model), actions in GROUP_PERMISSIONS.items():
        for action in actions:
            codename = f'{action}_{model}'
            try:
                permissions.append(
                    Permission.objects.get(content_type__app_label=app_label, codename=codename)
                )
            except Permission.DoesNotExist:
                raise CommandError(
                    f'Permissão {app_label}.{codename} não existe. Rode "python manage.py migrate" antes.'
                )
    return permissions


class Command(BaseCommand):
    """Cria o grupo "Loja" com exatamente as permissões da lista."""

    help = 'Cria ou atualiza o grupo "Loja" (catálogo e pedidos, sem dados de contas).'

    def handle(self, *args, **options):
        """get_or_create + set(): roda quantas vezes quiser, o resultado é o mesmo."""
        group, created = Group.objects.get_or_create(name=GROUP_NAME)
        # set() troca as permissões do grupo pela lista exata (tira as que sobram).
        group.permissions.set(get_group_permissions())
        action = 'criado' if created else 'atualizado'
        self.stdout.write(self.style.SUCCESS(
            f'Grupo "{GROUP_NAME}" {action} com {group.permissions.count()} permissões.'
        ))
