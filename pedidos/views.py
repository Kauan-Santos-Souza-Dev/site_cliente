"""Views de pedido: checkout (formulário) e confirmação."""

from django.contrib import messages
from django.shortcuts import redirect, render

from carrinho.cart import Cart
from contas.decorators import verified_email_required

from .checkout import OutOfStockError, create_order
from .forms import CheckoutForm
from .models import Order
from .rate_limit import register_order, too_many_orders
from .whatsapp import build_whatsapp_url

# Chave da sessão com o número do último pedido feito neste navegador.
LAST_ORDER_SESSION_KEY = 'last_order_id'


@verified_email_required
def checkout(request):
    """GET: mostra o formulário. POST: cria o pedido e vai para a confirmação.

    Só para quem está logada e já confirmou o e-mail (decisão 72). Navegar e
    montar o carrinho continuam livres para visitantes (decisão 55).
    """
    cart = Cart(request)
    items = cart.items()

    # Não dá para finalizar com o carrinho vazio ou com estoque em falta.
    if not items:
        messages.error(request, 'Seu carrinho está vazio.')
        return redirect('cart_detail')
    if any(item['stock_problem'] for item in items):
        messages.error(request, 'Ajuste as quantidades marcadas antes de finalizar.')
        return redirect('cart_detail')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if too_many_orders(request):
            # Proteção contra pedidos em massa (veja pedidos/rate_limit.py).
            # Nada é salvo; o formulário volta preenchido, com o aviso.
            messages.error(
                request,
                'Recebemos muitos pedidos deste aparelho em pouco tempo. '
                'Fale com a gente pelo WhatsApp.',
            )
        elif form.is_valid():
            try:
                order = create_order(cart, form)
            except OutOfStockError as error:
                # Nada foi salvo (transaction.atomic desfez tudo).
                messages.error(request, str(error))
                return redirect('cart_detail')
            # Só pedidos criados de verdade contam para o limite.
            register_order(request)
            cart.clear()
            # Guardamos o número do pedido na sessão: só este navegador pode
            # ver a página de confirmação, que mostra nome e endereço.
            request.session[LAST_ORDER_SESSION_KEY] = order.pk
            return redirect('order_confirmation')
    else:
        form = CheckoutForm()

    context = {
        'form': form,
        'items': items,
        'total': sum(item['subtotal'] for item in items),
    }
    return render(request, 'pedidos/checkout.html', context)


def order_confirmation(request):
    """Página "Pedido recebido" com o botão que abre o WhatsApp da loja.

    Não há número de pedido na URL: o pedido vem da sessão. Assim ninguém
    consegue ver o pedido (e o endereço) de outra pessoa trocando o número.
    """
    order_id = request.session.get(LAST_ORDER_SESSION_KEY)
    order = Order.objects.filter(pk=order_id).prefetch_related('items').first()
    if order is None:
        return redirect('home')

    context = {
        'order': order,
        'whatsapp_url': build_whatsapp_url(order),
    }
    return render(request, 'pedidos/confirmation.html', context)
