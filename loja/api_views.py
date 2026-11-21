"""Views da API pública (somente leitura).

Aqui usamos as classes genéricas do DRF (ListAPIView, RetrieveAPIView):
elas já fazem paginação, checagem de permissão e conversão para JSON.
Basta dizer DE ONDE vêm os dados (queryset) e COMO viram JSON (serializer).

Por que são somente leitura? ListAPIView e RetrieveAPIView só respondem a
GET (e HEAD/OPTIONS). Um POST, PUT ou DELETE recebe "405 Método não
permitido". Cadastrar e editar produtos é só pelo Django Admin.
"""

from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from .models import Category
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)
from .views import active_products


class CategoryListAPIView(ListAPIView):
    """GET /api/categorias/ — lista as categorias."""

    # AllowAny declarado de propósito: a permissão padrão do projeto é
    # IsAdminUser (ver REST_FRAMEWORK em config/settings.py).
    permission_classes = [AllowAny]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    # Só existem 3 categorias: não precisa dividir em páginas.
    pagination_class = None


class ProductListAPIView(ListAPIView):
    """GET /api/produtos/ — lista produtos ativos.

    Filtros opcionais: ?categoria=vestidos e ?destaque=true
    """

    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        """Monta a consulta: produtos ativos + filtros da URL."""
        # Reaproveita a mesma consulta das páginas do site (com prefetch).
        products = active_products()

        category_slug = self.request.query_params.get('categoria')
        if category_slug:
            # Categoria inexistente devolve lista vazia (comum em APIs).
            products = products.filter(category__slug=category_slug)

        if self.request.query_params.get('destaque') == 'true':
            products = products.filter(is_featured=True)

        return products


class ProductDetailAPIView(RetrieveAPIView):
    """GET /api/produtos/<slug>/ — detalhes de um produto ativo."""

    permission_classes = [AllowAny]
    serializer_class = ProductDetailSerializer
    # Busca pelo slug (da URL) em vez do id. Produto inativo dá 404.
    lookup_field = 'slug'

    def get_queryset(self):
        """Só produtos ativos podem ser detalhados."""
        return active_products()
