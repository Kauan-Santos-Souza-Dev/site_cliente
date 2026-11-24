"""Models do catálogo (categoria, produto, variação de tamanho, imagem) e a configuração da loja."""

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from .validators import validate_image_file


class Category(models.Model):
    """Categoria fixa do catálogo (Vestidos, Saias, Conjuntos)."""

    name = models.CharField('nome', max_length=60)
    # O slug é o nome "amigável para URL" (ex.: "vestidos"), usado no filtro.
    slug = models.SlugField('slug', unique=True)

    class Meta:
        verbose_name = 'categoria'
        verbose_name_plural = 'categorias'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Peça de roupa à venda. Estoque e tamanhos ficam em ProductVariant."""

    # PROTECT: o banco impede apagar uma categoria que ainda tem produtos.
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name='categoria',
    )
    name = models.CharField('nome', max_length=120)
    slug = models.SlugField('slug', unique=True)
    description = models.TextField('descrição', blank=True)
    # Dinheiro sempre em DecimalField (float erra centavos).
    price = models.DecimalField('preço (R$)', max_digits=8, decimal_places=2)
    is_featured = models.BooleanField('destaque na página inicial', default=False)
    # is_active permite ocultar o produto sem apagá-lo.
    is_active = models.BooleanField('ativo', default=True)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'produto'
        verbose_name_plural = 'produtos'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """Endereço da página do produto no site.

        É uma convenção do Django: os templates usam {{ product.get_absolute_url }}
        e o admin mostra o botão "Ver no site" automaticamente.
        """
        return reverse('product_detail', args=[self.slug])

    @property
    def main_image(self):
        """Retorna a imagem principal; se não houver, a primeira; senão None."""
        images = list(self.images.all())  # usa o cache se houver prefetch
        for image in images:
            if image.is_main:
                return image
        return images[0] if images else None

    def sorted_variants(self):
        """Tamanhos na ordem da lista SIZE_CHOICES (P, M, G, GG), não alfabética."""
        size_order = [code for code, _label in ProductVariant.SIZE_CHOICES]
        return sorted(self.variants.all(), key=lambda v: size_order.index(v.size))

    @property
    def total_stock(self):
        """Soma do estoque de todos os tamanhos."""
        return sum(variant.stock for variant in self.variants.all())


class ProductVariant(models.Model):
    """Um tamanho de um produto, com estoque próprio. Sem variação de cor."""

    SIZE_CHOICES = [
        ('P', 'P'),
        ('M', 'M'),
        ('G', 'G'),
        ('GG', 'GG'),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
        verbose_name='produto',
    )
    size = models.CharField('tamanho', max_length=2, choices=SIZE_CHOICES)
    stock = models.PositiveIntegerField('estoque', default=0)

    class Meta:
        verbose_name = 'variação (tamanho)'
        verbose_name_plural = 'variações (tamanhos)'
        # Não pode haver dois "M" para o mesmo produto.
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'size'], name='unique_size_per_product'
            )
        ]

    def __str__(self):
        return f'{self.product.name} — {self.size}'


class ProductImage(models.Model):
    """Foto do produto. Um produto pode ter várias, com uma principal."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='produto',
    )
    image = models.ImageField(
        'imagem', upload_to='produtos/', validators=[validate_image_file]
    )
    # Texto alternativo: acessibilidade (leitores de tela) e SEO.
    alt_text = models.CharField('texto alternativo', max_length=150, blank=True)
    is_main = models.BooleanField('imagem principal', default=False)

    class Meta:
        verbose_name = 'imagem'
        verbose_name_plural = 'imagens'
        ordering = ['-is_main', 'id']

    def __str__(self):
        return f'Imagem de {self.product.name}'

    def save(self, *args, **kwargs):
        """Salva e garante que só uma imagem do produto seja a principal."""
        super().save(*args, **kwargs)
        if self.is_main:
            # Desmarca as outras imagens do mesmo produto.
            ProductImage.objects.filter(product=self.product).exclude(
                pk=self.pk
            ).update(is_main=False)


class StoreSettings(models.Model):
    """Configurações gerais da loja, editáveis no admin (v2 Etapa 5, decisão 89).

    É um "singleton": existe UMA linha só (id=1). Em vez de valores fixos no
    código, a dona muda no admin, sem precisar de programador. Use sempre
    StoreSettings.load() para ler.

    A v2 Etapa 6 acrescenta aqui as regras de parcelamento.
    """

    # Quanto tempo as peças ficam reservadas para um pedido não pago (decisão 58).
    reservation_minutes = models.PositiveIntegerField(
        'reserva do estoque (minutos)',
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(24 * 60)],
        help_text='Tempo para pagar. Depois disso o pedido expira e as peças voltam ao estoque. '
                  'Entre 5 e 1440 minutos.',
    )
    # Frete grátis a partir deste valor em produtos (decisão 54). Vazio = nunca grátis.
    free_shipping_threshold = models.DecimalField(
        'frete grátis a partir de (R$)',
        max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Soma dos produtos (sem frete). Deixe vazio para não ter frete grátis.',
    )
    free_shipping_is_provisional = models.BooleanField(
        'valor do frete grátis é PROVISÓRIO', default=True,
        help_text='Desmarque quando a dona confirmar o valor real.',
    )

    class Meta:
        verbose_name = 'configuração da loja'
        verbose_name_plural = 'configuração da loja'

    def __str__(self):
        return 'Configuração da loja'

    def save(self, *args, **kwargs):
        """Força o id 1: nunca existe uma segunda linha de configuração."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Devolve a configuração (cria com os valores padrão se ainda não existir)."""
        settings_row, _created = cls.objects.get_or_create(pk=1)
        return settings_row
