"""Funções de apoio para os testes de todos os apps (não é usado pelo site)."""

from django.contrib.auth import get_user_model
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

# Senha que passa em todos os validadores (10+ caracteres, não comum, não só números).
GOOD_PASSWORD = 'Lirio-do-campo-42'


def make_customer(email='cliente@example.com', verified=True, **extra):
    """Cria uma conta de cliente (por padrão, com e-mail já verificado)."""
    return get_user_model().objects.create_user(
        email=email, password=GOOD_PASSWORD, email_verified=verified, **extra,
    )


def login_admin(client, user):
    """Entra no admin como se a conta tivesse passado pelo 2FA.

    force_login pula a senha; depois gravamos na sessão o dispositivo 2FA
    "usado", que é exatamente o que o django-otp faz quando o código de
    6 dígitos confere. Só para testes: no site, o código é obrigatório.
    """
    device = TOTPDevice.objects.create(user=user, name='Teste', confirmed=True)
    client.force_login(user)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return device


# Endereço de entrega válido, já só com dígitos (como fica no banco).
ORDER_ADDRESS = {
    'customer_name': 'Maria da Silva',
    'phone': '11912345678',
    'cep': '01234567',
    'street': 'Rua das Flores',
    'number': '100',
    'complement': 'Apto 12',
    'neighborhood': 'Centro',
    'city': 'São Paulo',
    'state': 'SP',
}


def make_variant(slug='vestido-teste', price='150.00', size='M', stock=5):
    """Cria um produto ativo (categoria Vestidos) com um tamanho e devolve a variação."""
    from loja.models import Category, Product, ProductVariant

    product = Product.objects.create(
        category=Category.objects.get(slug='vestidos'),
        name=f'Produto {slug}', slug=slug, price=price,
    )
    return ProductVariant.objects.create(product=product, size=size, stock=stock)


def make_order(user=None, status='aguardando_pagamento', variant=None, quantity=1, **fields):
    """Cria um pedido com 1 item, DIRETO no banco (sem passar pelo checkout).

    Simula um pedido já feito: o estoque da variação NÃO é descontado aqui;
    o teste escolhe o estoque "depois da compra" ao criar a variação.
    """
    from pedidos.models import Order, OrderItem

    order = Order.objects.create(user=user, status=status, **{**ORDER_ADDRESS, **fields})
    OrderItem.objects.create(
        order=order, variant=variant,
        product_name=variant.product.name if variant else 'Peça apagada',
        size=variant.size if variant else 'M',
        unit_price=variant.product.price if variant else '100.00',
        quantity=quantity,
    )
    return order
