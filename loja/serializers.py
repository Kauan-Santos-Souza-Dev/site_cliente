"""Serializers da API: convertem os models em JSON.

Um serializer funciona como um "formulário ao contrário": em vez de receber
dados do usuário, ele pega um objeto do banco e escolhe quais campos viram
JSON. Aqui os campos são sempre listados um a um (nunca '__all__'), para que
nenhum campo interno (como o estoque exato ou is_active) vaze por acidente.
"""

from rest_framework import serializers

from .models import Category, Product, ProductImage, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    """Categoria: Vestidos, Saias ou Conjuntos."""

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class ProductImageSerializer(serializers.ModelSerializer):
    """Foto do produto, com endereço completo (http://.../media/...)."""

    # source='image': o campo do model se chama "image", mas no JSON vira "url".
    # O ImageField do DRF monta a URL completa usando o request do contexto.
    url = serializers.ImageField(source='image')

    class Meta:
        model = ProductImage
        fields = ['url', 'alt_text', 'is_main']


class ProductVariantSerializer(serializers.ModelSerializer):
    """Tamanho do produto. Mostra só se está disponível, nunca o estoque exato."""

    # SerializerMethodField: o valor vem do método get_<nome do campo>.
    available = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ['size', 'available']

    def get_available(self, variant):
        """True se ainda há pelo menos uma peça neste tamanho."""
        return variant.stock > 0


class ProductListSerializer(serializers.ModelSerializer):
    """Produto resumido, para listagens (sem descrição e sem todas as fotos)."""

    # Serializer dentro de serializer: a categoria aparece como objeto no JSON.
    category = CategorySerializer()
    main_image = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    # price: o DRF entrega Decimal como TEXTO ("199.90"), e não como número.
    # Assim nenhum centavo se perde: em JavaScript, 0.1 + 0.2 dá 0.30000000000000004.

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'category', 'price', 'is_featured',
            'main_image', 'url',
        ]

    def get_main_image(self, product):
        """URL completa da foto principal, ou None se o produto não tem foto."""
        image = product.main_image
        if image is None:
            return None
        return self.build_absolute_url(image.image.url)

    def get_url(self, product):
        """Endereço da página do produto no site."""
        return self.build_absolute_url(product.get_absolute_url())

    def build_absolute_url(self, path):
        """Transforma "/produto/x/" em "http://dominio/produto/x/".

        O request é entregue pela view no "context" do serializer.
        """
        request = self.context.get('request')
        return request.build_absolute_uri(path) if request else path


class ProductDetailSerializer(ProductListSerializer):
    """Produto completo: tudo da listagem + descrição, fotos e tamanhos."""

    images = ProductImageSerializer(many=True)  # many=True: é uma lista
    variants = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            'description', 'images', 'variants',
        ]

    def get_variants(self, product):
        """Tamanhos na ordem P, M, G, GG."""
        return ProductVariantSerializer(product.sorted_variants(), many=True).data
