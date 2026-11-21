"""Testes do catálogo: models, validadores, páginas e API."""

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product, ProductImage, ProductVariant
from .validators import MAX_IMAGE_SIZE, validate_image_file


class CatalogModelsTest(TestCase):
    """Regras dos models: categorias fixas, tamanho único e imagem principal."""

    def setUp(self):
        # As categorias fixas vêm da migration de dados (0002).
        self.category = Category.objects.get(slug='vestidos')
        self.product = Product.objects.create(
            category=self.category, name='Vestido Teste', slug='vestido-teste',
            price='149.90',
        )

    def test_categorias_fixas_existem(self):
        """A migration cria Vestidos, Saias e Conjuntos."""
        slugs = set(Category.objects.values_list('slug', flat=True))
        self.assertEqual(slugs, {'vestidos', 'saias', 'conjuntos'})

    def test_tamanho_nao_repete_no_mesmo_produto(self):
        """Dois tamanhos "M" no mesmo produto violam a restrição do banco."""
        ProductVariant.objects.create(product=self.product, size='M', stock=3)
        with self.assertRaises(IntegrityError):
            # atomic evita que o erro quebre a transação do teste.
            with transaction.atomic():
                ProductVariant.objects.create(
                    product=self.product, size='M', stock=1
                )

    def test_estoque_total_soma_os_tamanhos(self):
        ProductVariant.objects.create(product=self.product, size='P', stock=2)
        ProductVariant.objects.create(product=self.product, size='G', stock=5)
        self.assertEqual(self.product.total_stock, 7)

    def test_so_uma_imagem_principal(self):
        """Marcar uma nova imagem como principal desmarca a anterior."""
        primeira = ProductImage.objects.create(
            product=self.product, image='produtos/a.jpg', is_main=True
        )
        segunda = ProductImage.objects.create(
            product=self.product, image='produtos/b.jpg', is_main=True
        )
        primeira.refresh_from_db()
        self.assertFalse(primeira.is_main)
        self.assertTrue(segunda.is_main)
        self.assertEqual(self.product.main_image, segunda)

    def test_categoria_com_produtos_nao_pode_ser_apagada(self):
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.category.delete()


class AdminAccessTest(TestCase):
    """O painel da loja exige login."""

    def test_admin_sem_login_vai_para_a_tela_de_login(self):
        response = self.client.get(reverse('admin:loja_product_changelist'))
        # 302 = redirecionamento; a lista de produtos não é mostrada.
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response['Location'])


class BaseTemplateTest(TestCase):
    """Template base: rodapé e dados da loja (etapa 3)."""

    def setUp(self):
        # self.client simula um navegador fazendo requisições ao site.
        self.response = self.client.get('/')

    def test_pagina_inicial_responde(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertTemplateUsed(self.response, 'base.html')

    def test_rodape_usa_dados_de_settings(self):
        """O link do WhatsApp vem de settings, via context processor."""
        self.assertContains(self.response, f'https://wa.me/{settings.WHATSAPP_NUMBER}')
        self.assertContains(self.response, settings.STORE_MOTTO)

    def test_site_nao_mostra_cnpj(self):
        """A loja ainda não tem CNPJ: nada disso pode aparecer no site."""
        self.assertNotContains(self.response, 'CNPJ')


class ImageValidatorTest(TestCase):
    """Validação de upload: formato e tamanho."""

    def test_aceita_png_pequeno(self):
        arquivo = SimpleUploadedFile('foto.png', b'x' * 100)
        validate_image_file(arquivo)  # não deve lançar erro

    def test_rejeita_formato_gif(self):
        arquivo = SimpleUploadedFile('foto.gif', b'x' * 100)
        with self.assertRaises(ValidationError):
            validate_image_file(arquivo)

    def test_rejeita_imagem_maior_que_2mb(self):
        arquivo = SimpleUploadedFile('foto.jpg', b'x' * (MAX_IMAGE_SIZE + 1))
        with self.assertRaises(ValidationError):
            validate_image_file(arquivo)


class PagesTest(TestCase):
    """Páginas públicas da etapa 4: início, catálogo, produto e institucionais."""

    def setUp(self):
        vestidos = Category.objects.get(slug='vestidos')
        saias = Category.objects.get(slug='saias')
        # Um produto ativo e em destaque, um ativo comum e um inativo.
        self.destaque = Product.objects.create(
            category=vestidos, name='Vestido Destaque', slug='vestido-destaque',
            price='199.90', is_featured=True,
        )
        self.saia = Product.objects.create(
            category=saias, name='Saia Comum', slug='saia-comum', price='99.90',
        )
        self.inativo = Product.objects.create(
            category=vestidos, name='Vestido Oculto', slug='vestido-oculto',
            price='149.90', is_featured=True, is_active=False,
        )

    # --- Página inicial ---------------------------------------------------
    def test_inicio_mostra_so_destaques_ativos(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Vestido Destaque')
        self.assertNotContains(response, 'Saia Comum')  # não é destaque
        self.assertNotContains(response, 'Vestido Oculto')  # inativo

    # --- Catálogo ---------------------------------------------------------
    def test_catalogo_lista_ativos_e_esconde_inativos(self):
        response = self.client.get(reverse('catalog'))
        self.assertContains(response, 'Vestido Destaque')
        self.assertContains(response, 'Saia Comum')
        self.assertNotContains(response, 'Vestido Oculto')

    def test_catalogo_filtra_por_categoria(self):
        response = self.client.get(reverse('catalog'), {'categoria': 'saias'})
        self.assertContains(response, 'Saia Comum')
        self.assertNotContains(response, 'Vestido Destaque')

    def test_categoria_inexistente_da_404(self):
        response = self.client.get(reverse('catalog'), {'categoria': 'bolsas'})
        self.assertEqual(response.status_code, 404)

    def test_pagina_invalida_nao_quebra(self):
        """?pagina=abc cai na primeira página em vez de dar erro."""
        response = self.client.get(reverse('catalog'), {'pagina': 'abc'})
        self.assertEqual(response.status_code, 200)

    # --- Produto ----------------------------------------------------------
    def test_produto_abre_com_preco_e_tamanhos(self):
        ProductVariant.objects.create(product=self.destaque, size='M', stock=2)
        ProductVariant.objects.create(product=self.destaque, size='G', stock=0)
        response = self.client.get(self.destaque.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'R$ 199,90')  # formato brasileiro
        # O tamanho G está sem estoque: aparece riscado e com aviso.
        self.assertContains(response, 'tamanho--esgotado')
        self.assertContains(response, '(esgotado)')

    def test_produto_inativo_da_404(self):
        response = self.client.get(self.inativo.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    # --- Páginas institucionais ------------------------------------------
    def test_paginas_institucionais_respondem(self):
        for name in ['about', 'contact', 'privacy']:
            # subTest mostra qual página falhou, se alguma falhar.
            with self.subTest(pagina=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)

    def test_privacidade_lista_os_dados_coletados(self):
        response = self.client.get(reverse('privacy'))
        self.assertContains(response, 'telefone/WhatsApp')
        self.assertContains(response, 'endereço de entrega')


class ProductAPITest(TestCase):
    """API pública de leitura (etapa 5): /api/categorias/ e /api/produtos/."""

    def setUp(self):
        # O limite de requisições (throttling) conta acessos no cache.
        # Limpamos para um teste não "gastar" o limite do outro.
        cache.clear()
        vestidos = Category.objects.get(slug='vestidos')
        saias = Category.objects.get(slug='saias')
        self.vestido = Product.objects.create(
            category=vestidos, name='Vestido API', slug='vestido-api',
            price='199.90', is_featured=True, description='Vestido longo.',
        )
        ProductVariant.objects.create(product=self.vestido, size='G', stock=0)
        ProductVariant.objects.create(product=self.vestido, size='P', stock=3)
        self.saia = Product.objects.create(
            category=saias, name='Saia API', slug='saia-api', price='99.90',
        )
        self.inativo = Product.objects.create(
            category=vestidos, name='Inativo API', slug='inativo-api',
            price='10.00', is_active=False,
        )

    def product_slugs(self, response):
        """Slugs dos produtos de uma resposta paginada (lista em "results")."""
        return [item['slug'] for item in response.json()['results']]

    def test_lista_categorias(self):
        response = self.client.get(reverse('api_categories'))
        self.assertEqual(response.status_code, 200)
        slugs = {item['slug'] for item in response.json()}
        self.assertEqual(slugs, {'vestidos', 'saias', 'conjuntos'})

    def test_lista_produtos_so_ativos_e_paginada(self):
        response = self.client.get(reverse('api_products'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Resposta paginada do DRF: count, next, previous e results.
        self.assertEqual(data['count'], 2)
        self.assertNotIn('inativo-api', self.product_slugs(response))

    def test_filtro_por_categoria(self):
        response = self.client.get(reverse('api_products'), {'categoria': 'saias'})
        self.assertEqual(self.product_slugs(response), ['saia-api'])

    def test_filtro_por_destaque(self):
        response = self.client.get(reverse('api_products'), {'destaque': 'true'})
        self.assertEqual(self.product_slugs(response), ['vestido-api'])

    def test_preco_vem_como_texto(self):
        """Decimal vira texto no JSON para não perder centavos."""
        response = self.client.get(reverse('api_product_detail', args=['vestido-api']))
        self.assertEqual(response.json()['price'], '199.90')

    def test_detalhe_mostra_disponibilidade_sem_estoque_exato(self):
        response = self.client.get(reverse('api_product_detail', args=['vestido-api']))
        self.assertEqual(response.status_code, 200)
        variants = response.json()['variants']
        # Ordem P, M, G, GG (e não a ordem de cadastro).
        self.assertEqual(variants, [
            {'size': 'P', 'available': True},
            {'size': 'G', 'available': False},
        ])
        # O número de peças em estoque nunca aparece na API.
        self.assertNotIn('stock', response.content.decode())

    def test_detalhe_de_produto_inativo_da_404(self):
        response = self.client.get(reverse('api_product_detail', args=['inativo-api']))
        self.assertEqual(response.status_code, 404)

    def test_api_nao_aceita_escrita(self):
        """Ninguém cria, altera ou apaga produtos pela API."""
        url = reverse('api_products')
        response = self.client.post(url, {'name': 'Hacker', 'price': '1.00'})
        self.assertEqual(response.status_code, 405)
        detail = reverse('api_product_detail', args=['vestido-api'])
        self.assertEqual(self.client.delete(detail).status_code, 405)
        self.assertTrue(Product.objects.filter(slug='vestido-api').exists())
