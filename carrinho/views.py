"""Views do carrinho: ver, adicionar, alterar quantidade e remover.

Padrão Post/Redirect/Get (PRG): toda view que MUDA o carrinho só aceita
POST e, no final, redireciona para outra página. Assim, se a cliente apertar
F5, o navegador recarrega a página de destino (um GET) e não envia o
formulário de novo — nada é adicionado duas vezes.

Mensagens (django.contrib.messages): guardam um aviso para a PRÓXIMA página
exibida. Por isso funcionam bem junto com o redirecionamento.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from loja.models import ProductVariant
from loja.views import active_products

from .cart import Cart
from .forms import AddToCartForm, UpdateQuantityForm, first_error


def cart_detail(request):
    """Página do carrinho: itens, quantidades e total."""
    cart = Cart(request)
    items = cart.items()
    context = {
        'items': items,
        # Soma calculada aqui a partir da mesma lista (evita consultar duas vezes).
        'total': sum(item['subtotal'] for item in items),
        'has_stock_problem': any(item['stock_problem'] for item in items),
    }
    return render(request, 'carrinho/cart_detail.html', context)


# require_POST: um GET nesta URL recebe "405 Método não permitido".
# O formulário da página tem {% csrf_token %}: o Django recusa POST sem ele
# (proteção contra outro site enviar formulários em nome da cliente).
@require_POST
def cart_add(request, product_id):
    """Adiciona um tamanho de um produto ao carrinho."""
    product = get_object_or_404(active_products(), id=product_id)
    form = AddToCartForm(request.POST, product=product)

    if not form.is_valid():
        messages.error(request, first_error(form))
        return redirect(product)  # redirect(objeto) usa get_absolute_url()

    variant = form.cleaned_data['variant']
    quantity = form.cleaned_data['quantity']
    error = Cart(request).add(variant, quantity)
    if error:
        messages.error(request, error)
        return redirect(product)

    messages.success(request, f'{product.name} ({variant.size}) foi adicionado ao carrinho.')
    return redirect('cart_detail')


@require_POST
def cart_update(request, variant_id):
    """Troca a quantidade de um item do carrinho."""
    variant = get_object_or_404(ProductVariant.objects.select_related('product'), id=variant_id)
    form = UpdateQuantityForm(request.POST)

    if not form.is_valid():
        messages.error(request, first_error(form))
        return redirect('cart_detail')

    error = Cart(request).update(variant, form.cleaned_data['quantity'])
    if error:
        messages.error(request, error)
    else:
        messages.success(request, 'Quantidade atualizada.')
    return redirect('cart_detail')


@require_POST
def cart_remove(request, variant_id):
    """Tira um item do carrinho."""
    variant = get_object_or_404(ProductVariant.objects.select_related('product'), id=variant_id)
    Cart(request).remove(variant)
    messages.success(request, f'{variant.product.name} ({variant.size}) saiu do carrinho.')
    return redirect('cart_detail')
