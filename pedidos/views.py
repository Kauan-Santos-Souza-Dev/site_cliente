"""Views de pedido: checkout, "Meus pedidos" e detalhe do pedido."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from carrinho.cart import Cart
from contas.decorators import verified_email_required
from loja.models import StoreSettings
from pagamentos import gateway
from pagamentos.models import Payment

from .checkout import OutOfStockError, create_order
from .forms import CheckoutForm
from .installments import calculate_installments, get_installment_limit
from .models import ShippingRate
from .rate_limit import register_order, too_many_orders
from .reservations import cancel_order_by_customer, expire_overdue_orders
from .shipping import ShippingUnavailableError, shipping_table
from .whatsapp import build_whatsapp_url


@verified_email_required
def checkout(request):
    """GET: mostra o formulário. POST: cria o pedido e vai para o detalhe dele.

    Só para quem está logada e já confirmou o e-mail (decisões 55 e 72).
    Navegar e montar o carrinho continuam livres para visitantes.
    """
    # Libera reservas vencidas antes de conferir o estoque (decisão 88).
    expire_overdue_orders()
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
                order = create_order(cart, form, request.user)
            except OutOfStockError as error:
                # Nada foi salvo (transaction.atomic desfez tudo).
                messages.error(request, str(error))
                return redirect('cart_detail')
            except ShippingUnavailableError as error:
                # UF sem frete: o erro aparece no campo UF e nada é salvo.
                form.add_error('state', str(error))
            else:
                # Só pedidos criados de verdade contam para o limite.
                register_order(request)
                cart.clear()
                messages.success(request, f'Pedido nº {order.pk} recebido!')
                # O número na URL é seguro: order_detail só mostra pedidos
                # da conta logada (decisão 91).
                return redirect('order_detail', pk=order.pk)
    else:
        # Já sugere o nome da conta; a cliente pode trocar (ex.: presente).
        form = CheckoutForm(initial={'customer_name': request.user.get_full_name()})

    items_total = sum(item['subtotal'] for item in items)
    context = {
        'form': form,
        'items': items,
        'items_total': items_total,
        # Tabela de frete: para o JavaScript (shipping_table, em texto) e para
        # a lista visível sem JavaScript (shipping_rates). Só para EXIBIR: o
        # frete cobrado é calculado de novo no servidor, em create_order().
        'shipping_table': shipping_table(),
        'shipping_rates': ShippingRate.objects.order_by('state'),
        # Parcelas no cartão: só INFORMAÇÃO (estimativa sobre o valor dos produtos,
        # sem frete). O limite de verdade é calculado de novo no servidor, sobre o
        # total do pedido, quando o pagamento for criado (Etapa 8, decisão 99).
        'installments': calculate_installments(
            items_total, get_installment_limit([item['product'] for item in items])
        ),
        'free_shipping_threshold': StoreSettings.load().free_shipping_threshold,
    }
    return render(request, 'pedidos/checkout.html', context)


@login_required
def my_orders(request):
    """Lista "Meus pedidos": SÓ os pedidos da conta logada.

    Contra IDOR (Insecure Direct Object Reference): a consulta parte sempre
    de request.user.orders, nunca de Order.objects.all().
    """
    expire_overdue_orders(user=request.user)
    orders = request.user.orders.prefetch_related('items')
    return render(request, 'pedidos/my_orders.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    """Detalhe de um pedido da conta logada.

    get_object_or_404 com pk E user: se o número for de outra cliente (ou não
    existir), a resposta é a MESMA: 404. Um 403 ("proibido") confirmaria que
    aquele pedido existe.
    """
    expire_overdue_orders(user=request.user)
    order = get_object_or_404(
        request.user.orders.prefetch_related('items'), pk=pk
    )
    context = {
        'order': order,
        'whatsapp_url': build_whatsapp_url(order),
        # Pix (v2 Etapa 7): o botão só aparece com o Mercado Pago configurado;
        # se o Pix já foi gerado, o botão leva de volta ao QR Code.
        'online_payment_available': gateway.is_configured(),
        'pix_payment': order.payments.filter(method=Payment.Method.PIX).exclude(pix_code='').first(),
    }
    return render(request, 'pedidos/order_detail.html', context)


@login_required
@require_POST
def cancel_order(request, pk):
    """A cliente cancela um pedido dela que ainda aguarda pagamento.

    - @require_POST: cancelar muda dados, então nunca por GET (um link ou um
      robô poderia cancelar sem querer). O CSRF do Django protege o POST.
    - A busca é pela conta logada (contra IDOR): pedido de outra cliente dá 404.
    - Quem devolve o estoque, com trava, é cancel_order_by_customer.
    """
    # Se o prazo já venceu, o pedido vira "expirado" e a mensagem fica correta.
    expire_overdue_orders(user=request.user)
    order = get_object_or_404(request.user.orders, pk=pk)
    if cancel_order_by_customer(request.user, order.pk):
        messages.success(request, f'Pedido nº {order.pk} cancelado. As peças voltaram para a loja.')
    else:
        messages.error(request, f'O pedido nº {order.pk} não pode mais ser cancelado.')
    return redirect('my_orders')
