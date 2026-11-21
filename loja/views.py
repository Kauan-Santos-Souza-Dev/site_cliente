"""Views das páginas públicas da loja.

Uma view é uma função que recebe o pedido do navegador (request) e devolve
uma resposta, quase sempre uma página HTML montada com render().
Usamos funções simples, e não as classes genéricas do Django, porque o fluxo
fica todo visível de cima para baixo (ver DECISIONS.md).
"""

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Category, Product

# Quantos produtos aparecem por página no catálogo.
PRODUCTS_PER_PAGE = 12
# Quantos destaques aparecem na página inicial.
FEATURED_LIMIT = 8


def active_products():
    """Produtos visíveis no site, já com categoria, imagens e tamanhos.

    Por que select_related e prefetch_related?
    Sem eles, o template faria 1 consulta para a lista e mais 1 consulta por
    produto para buscar a foto (e outra para o estoque). Com 12 produtos,
    seriam mais de 20 consultas: é o famoso problema "N+1".
    - select_related('category'): traz a categoria na MESMA consulta (JOIN).
      Serve para relações "para um" (ForeignKey).
    - prefetch_related('images', 'variants'): faz UMA consulta extra para todas
      as imagens e UMA para todas as variações. Serve para relações "para muitos".
    """
    return (
        Product.objects.filter(is_active=True)
        .select_related('category')
        .prefetch_related('images', 'variants')
    )


def home(request):
    """Página inicial: banner, categorias e produtos em destaque."""
    featured_products = active_products().filter(is_featured=True)[:FEATURED_LIMIT]
    context = {
        'categories': Category.objects.all(),
        'featured_products': featured_products,
    }
    return render(request, 'loja/home.html', context)


def catalog(request):
    """Catálogo com filtro opcional por categoria (?categoria=vestidos) e paginação."""
    products = active_products()
    current_category = None

    # request.GET guarda os parâmetros da URL depois do "?".
    category_slug = request.GET.get('categoria')
    if category_slug:
        # Se a categoria não existir, devolve a página 404 (não encontrada).
        current_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=current_category)

    # O Paginator divide a lista em páginas. get_page() é tolerante:
    # "?pagina=abc" ou um número grande demais devolvem uma página válida.
    paginator = Paginator(products, PRODUCTS_PER_PAGE)
    page = paginator.get_page(request.GET.get('pagina'))

    context = {
        'categories': Category.objects.all(),
        'current_category': current_category,
        'page': page,
    }
    return render(request, 'loja/catalog.html', context)


def product_detail(request, slug):
    """Página de um produto: fotos, preço, descrição e tamanhos."""
    # Produto inativo também dá 404: para o cliente, ele "não existe".
    product = get_object_or_404(active_products(), slug=slug)
    context = {
        'product': product,
        'images': product.images.all(),
        'variants': product.sorted_variants(),
    }
    return render(request, 'loja/product_detail.html', context)


def about(request):
    """Página Sobre a loja."""
    return render(request, 'loja/about.html')


def contact(request):
    """Página de Contato (só links: WhatsApp, Instagram e e-mail)."""
    return render(request, 'loja/contact.html')


def privacy(request):
    """Página de Política de Privacidade (LGPD)."""
    return render(request, 'loja/privacy.html')
