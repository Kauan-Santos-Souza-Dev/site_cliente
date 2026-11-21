"""Testes do carrinho na sessão (etapa 6).

self.client simula um navegador: ele guarda o cookie de sessão entre as
requisições, então o carrinho "lembra" o que foi adicionado no mesmo teste.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from loja.models import Category, Product, ProductVariant

from .cart import CART_SESSION_KEY


class CartTest(TestCase):
    """Adicionar, alterar, remover e conferir estoque e total."""

    def setUp(self):
        self.product = Product.objects.create(
            category=Category.objects.get(slug='vestidos'),
            name='Vestido Teste', slug='vestido-teste', price='100.00',
        )
        self.size_m = ProductVariant.objects.create(product=self.product, size='M', stock=3)
        self.size_g = ProductVariant.objects.create(product=self.product, size='G', stock=0)

    # --- Funções de apoio -----------------------------------------------------
    def add(self, variant, quantity=1, follow=False):
        """Envia o formulário "Adicionar ao carrinho" da página do produto."""
        url = reverse('cart_add', args=[variant.product.id])
        return self.client.post(
            url, {'variant': variant.id, 'quantity': quantity}, follow=follow
        )

    def cart_data(self):
        """O dicionário do carrinho guardado na sessão: {"id": quantidade}."""
        return self.client.session.get(CART_SESSION_KEY, {})

    # --- Adicionar -----------------------------------------------------------
    def test_adicionar_coloca_no_carrinho(self):
        response = self.add(self.size_m, 2)
        self.assertRedirects(response, reverse('cart_detail'))
        self.assertEqual(self.cart_data(), {str(self.size_m.id): 2})

    def test_adicionar_de_novo_soma_a_quantidade(self):
        self.add(self.size_m, 1)
        self.add(self.size_m, 2)
        self.assertEqual(self.cart_data()[str(self.size_m.id)], 3)

    def test_nao_passa_do_estoque(self):
        """Pedir 4 com estoque 3: recusa e diz quantas restam."""
        response = self.add(self.size_m, 4, follow=True)
        self.assertContains(response, 'Temos apenas 3 peças no tamanho M.')
        self.assertEqual(self.cart_data(), {})

    def test_soma_com_o_carrinho_tambem_respeita_estoque(self):
        """2 já no carrinho + 2 novas = 4 > 3: a segunda adição é recusada."""
        self.add(self.size_m, 2)
        self.add(self.size_m, 2)
        self.assertEqual(self.cart_data()[str(self.size_m.id)], 2)

    def test_tamanho_esgotado_e_recusado(self):
        response = self.add(self.size_g, 1, follow=True)
        self.assertContains(response, 'Este tamanho não está disponível.')
        self.assertEqual(self.cart_data(), {})

    def test_sem_tamanho_pede_para_escolher(self):
        url = reverse('cart_add', args=[self.product.id])
        response = self.client.post(url, {'quantity': 1}, follow=True)
        self.assertContains(response, 'Escolha um tamanho.')

    def test_produto_inativo_nao_pode_ser_adicionado(self):
        self.product.is_active = False
        self.product.save()
        response = self.add(self.size_m, 1)
        self.assertEqual(response.status_code, 404)

    def test_adicionar_por_get_nao_e_permitido(self):
        """Só POST muda o carrinho (GET recebe 405)."""
        response = self.client.get(reverse('cart_add', args=[self.product.id]))
        self.assertEqual(response.status_code, 405)

    # --- Alterar quantidade --------------------------------------------------
    def test_atualizar_quantidade(self):
        self.add(self.size_m, 1)
        self.client.post(reverse('cart_update', args=[self.size_m.id]), {'quantity': 3})
        self.assertEqual(self.cart_data()[str(self.size_m.id)], 3)

    def test_atualizar_acima_do_estoque_e_recusado(self):
        self.add(self.size_m, 1)
        response = self.client.post(
            reverse('cart_update', args=[self.size_m.id]), {'quantity': 10}, follow=True
        )
        self.assertContains(response, 'Temos apenas 3 peças')
        self.assertEqual(self.cart_data()[str(self.size_m.id)], 1)

    def test_quantidade_zero_e_recusada(self):
        self.add(self.size_m, 1)
        self.client.post(reverse('cart_update', args=[self.size_m.id]), {'quantity': 0})
        self.assertEqual(self.cart_data()[str(self.size_m.id)], 1)

    # --- Remover -------------------------------------------------------------
    def test_remover_tira_do_carrinho(self):
        self.add(self.size_m, 2)
        self.client.post(reverse('cart_remove', args=[self.size_m.id]))
        self.assertEqual(self.cart_data(), {})

    # --- Total e página ------------------------------------------------------
    def test_total_e_contador(self):
        self.add(self.size_m, 2)
        response = self.client.get(reverse('cart_detail'))
        self.assertEqual(response.context['total'], Decimal('200.00'))
        self.assertEqual(response.context['cart_count'], 2)
        self.assertContains(response, 'R$ 200,00')

    def test_total_usa_o_preco_atual_do_banco(self):
        """O carrinho não guarda preço: se a loja mudar o preço, o total muda."""
        self.add(self.size_m, 1)
        self.product.price = Decimal('80.00')
        self.product.save()
        response = self.client.get(reverse('cart_detail'))
        self.assertEqual(response.context['total'], Decimal('80.00'))

    def test_produto_desativado_some_do_carrinho(self):
        self.add(self.size_m, 1)
        self.product.is_active = False
        self.product.save()
        response = self.client.get(reverse('cart_detail'))
        self.assertEqual(response.context['items'], [])
        self.assertEqual(self.cart_data(), {})

    def test_estoque_que_baixou_mostra_aviso(self):
        """Se o estoque cair depois de adicionar, o item aparece marcado."""
        self.add(self.size_m, 3)
        self.size_m.stock = 1
        self.size_m.save()
        response = self.client.get(reverse('cart_detail'))
        self.assertTrue(response.context['items'][0]['stock_problem'])
        self.assertContains(response, 'Temos apenas 1 peça neste tamanho.')

    def test_carrinho_vazio(self):
        response = self.client.get(reverse('cart_detail'))
        self.assertContains(response, 'Seu carrinho está vazio.')

    def test_visitar_o_site_nao_cria_sessao(self):
        """Só quem usa o carrinho ganha sessão (o contador apenas lê)."""
        response = self.client.get(reverse('home'))
        self.assertNotIn('sessionid', response.cookies)
