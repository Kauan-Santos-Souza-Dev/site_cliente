"""Comando que cadastra os produtos de exemplo a partir das fotos de assets/.

Como usar:
    python manage.py carregar_exemplos

O que é um "management command"?
É um comando próprio que roda com `python manage.py <nome>`, igual ao
`migrate` ou ao `runserver`. O Django procura automaticamente arquivos em
<app>/management/commands/ e o nome do arquivo vira o nome do comando.
Cada comando é uma classe chamada Command, e o trabalho acontece em handle().

Os preços e estoques abaixo são FICTÍCIOS: ajuste depois pelo admin.
"""

from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from PIL import Image

from loja.models import Category, Product, ProductImage, ProductVariant

# Pasta com as fotos originais enviadas pela loja.
ASSETS_DIR = settings.BASE_DIR / 'assets'

# Maior lado da foto depois de convertida (em pixels).
MAX_IMAGE_SIDE = 1200

# Estoque fictício por tamanho, igual para todos os exemplos.
EXAMPLE_STOCK = {'P': 3, 'M': 5, 'G': 4, 'GG': 2}

# (arquivo em assets/, nome do produto, slug da categoria, preço, destaque?)
# O preço é texto para virar Decimal sem erro de arredondamento.
# "Morangue - Copia.png" fica de fora porque é a mesma foto de "Morangue.png".
EXAMPLE_PRODUCTS = [
    ('Conjunto_Jasmin.png', 'Conjunto Jasmin', 'conjuntos', '219.90', True),
    ('Conjunto_Perolado.png', 'Conjunto Perolado', 'conjuntos', '239.90', True),
    ('Vestido_Helena.png', 'Vestido Helena', 'vestidos', '229.90', True),
    ('Morangue.png', 'Vestido Morangue', 'vestidos', '189.90', True),
    ('Vestido_Cassia.png', 'Vestido Cássia', 'vestidos', '199.90', False),
    ('Daniela.png', 'Vestido Daniela', 'vestidos', '199.90', False),
    ('Fenix.png', 'Vestido Fênix', 'vestidos', '209.90', False),
    ('Melina.png', 'Vestido Melina', 'vestidos', '209.90', False),
    ('rochana.png', 'Vestido Rochana Preto', 'vestidos', '179.90', False),
    ('Vestido Rochana.png', 'Vestido Rochana Marrom', 'vestidos', '179.90', False),
    ('Rochê.png', 'Vestido Rochê', 'vestidos', '219.90', False),
    ('Sol.png', 'Vestido Sol', 'vestidos', '219.90', False),
    ('valierie.png', 'Vestido Valierie', 'vestidos', '219.90', False),
]


def convert_to_webp(path):
    """Abre a foto, reduz se for grande e devolve os bytes em formato WebP.

    WebP deixa o arquivo bem menor que PNG com qualidade parecida,
    o que faz o site carregar mais rápido no celular.
    """
    with Image.open(path) as image:
        # PNG pode ter transparência (RGBA); a foto final não precisa disso.
        image = image.convert('RGB')
        # thumbnail() reduz mantendo a proporção e nunca aumenta a foto.
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        buffer = BytesIO()  # um "arquivo" na memória
        image.save(buffer, format='WEBP', quality=82)
    return buffer.getvalue()


class Command(BaseCommand):
    """Cadastra os produtos de exemplo (pode rodar várias vezes sem duplicar)."""

    help = 'Cadastra os produtos de exemplo usando as fotos da pasta assets/.'

    def handle(self, *args, **options):
        """Percorre a lista de exemplos e cria os que ainda não existem."""
        created = 0
        for filename, name, category_slug, price, featured in EXAMPLE_PRODUCTS:
            slug = slugify(name)  # "Vestido Cássia" -> "vestido-cassia"

            # Idempotente: se já existe, não cria de novo.
            if Product.objects.filter(slug=slug).exists():
                self.stdout.write(f'Já existe, pulando: {name}')
                continue

            path = ASSETS_DIR / filename
            if not path.exists():
                self.stderr.write(f'Foto não encontrada, pulando: {path}')
                continue

            self.create_product(path, name, slug, category_slug, price, featured)
            created += 1
            self.stdout.write(f'Criado: {name}')

        self.stdout.write(self.style.SUCCESS(f'{created} produto(s) criado(s).'))

    @transaction.atomic
    def create_product(self, path, name, slug, category_slug, price, featured):
        """Cria o produto, a foto principal e os tamanhos de uma vez só.

        transaction.atomic: ou tudo é salvo, ou nada é. Se a conversão da foto
        falhar no meio, não sobra um produto "pela metade" no banco.
        """
        product = Product.objects.create(
            category=Category.objects.get(slug=category_slug),
            name=name,
            slug=slug,
            description=f'{name}: descrição de exemplo. Edite este texto no painel da loja.',
            price=price,
            is_featured=featured,
        )

        # ContentFile transforma os bytes em um "arquivo" que o ImageField aceita.
        # O Django salva o arquivo em media/produtos/ (upload_to do model).
        webp_bytes = convert_to_webp(path)
        ProductImage.objects.create(
            product=product,
            image=ContentFile(webp_bytes, name=f'{slug}.webp'),
            alt_text=f'Modelo usando {name}, foto de corpo inteiro',
            is_main=True,
        )

        for size, stock in EXAMPLE_STOCK.items():
            ProductVariant.objects.create(product=product, size=size, stock=stock)
