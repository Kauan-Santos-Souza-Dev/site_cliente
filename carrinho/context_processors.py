"""Context processor do carrinho: o contador de peças aparece em todas as páginas."""

from .cart import Cart


def cart_count(request):
    """Entrega `cart_count` aos templates. Não consulta o banco (só a sessão)."""
    return {'cart_count': Cart(request).count()}
