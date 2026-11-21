"""Testes de pedido (etapa 7): checkout, preço guardado, estoque e WhatsApp."""

from decimal import Decimal
from urllib.parse import unquote

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from loja.models import Category, Product, ProductVariant

from .forms import CheckoutForm
from .models import Order, OrderItem
from .rate_limit import MAX_ORDERS_PER_HOUR
from .whatsapp import build_whatsapp_url, format_brl

# Dados válidos do formulário de checkout (com máscara, como a cliente digita).
CUSTOMER_DATA = {
    'customer_name': 'Maria da Silva',
    'phone': '(11) 91234-5678',
    'cep': '01234-567',
    'street': 'Rua das Flores',
    'number': '100',
    'complement': 'Apto 12',
    'neighborhood': 'Centro',
    'city': 'São Paulo',
    'state': 'SP',
}


class CheckoutTest(TestCase):
    """Do carrinho ao pedido salvo no banco."""

    def setUp(self):
        # O contador do limite de pedidos fica no cache, que NÃO é apagado
        # entre um teste e outro (só o banco é). Limpamos para que pedidos
        # de um teste não contem no limite do próximo.
        cache.clear()
        self.product = Product.objects.create(
            category=Category.objects.get(slug='vestidos'),
            name='Vestido Teste', slug='vestido-teste', price='150.00',
        )
        self.variant = ProductVariant.objects.create(product=self.product, size='M', stock=5)

    def add_to_cart(self, quantity=2):
        """Coloca peças no carrinho pelo mesmo formulário da página do produto."""
        self.client.post(
            reverse('cart_add', args=[self.product.id]),
            {'variant': self.variant.id, 'quantity': quantity},
        )

    def checkout(self, data=CUSTOMER_DATA):
        """Envia o formulário de checkout."""
        return self.client.post(reverse('checkout'), data)

    # --- Pedido criado -------------------------------------------------------
    def test_checkout_cria_pedido_e_itens(self):
        self.add_to_cart(2)
        response = self.checkout()
        self.assertRedirects(response, reverse('order_confirmation'))

        order = Order.objects.get()
        self.assertEqual(order.status, Order.Status.NEW)
        self.assertIsNone(order.shipping_cost)  # frete a combinar na v1
        item = order.items.get()
        self.assertEqual((item.product_name, item.size, item.quantity), ('Vestido Teste', 'M', 2))
        self.assertEqual(order.total, Decimal('300.00'))

    def test_preco_fica_guardado_no_item(self):
        """Mudar o preço do produto depois NÃO muda o pedido já feito."""
        self.add_to_cart(1)
        self.checkout()
        self.product.price = Decimal('999.00')
        self.product.save()
        item = OrderItem.objects.get()
        self.assertEqual(item.unit_price, Decimal('150.00'))

    def test_estoque_e_descontado(self):
        self.add_to_cart(2)
        self.checkout()
        self.variant.refresh_from_db()  # relê o valor atual do banco
        self.assertEqual(self.variant.stock, 3)

    def test_carrinho_e_esvaziado(self):
        self.add_to_cart(1)
        self.checkout()
        self.assertEqual(self.client.session.get('cart'), {})

    def test_telefone_e_cep_salvos_so_com_digitos(self):
        self.add_to_cart(1)
        self.checkout()
        order = Order.objects.get()
        self.assertEqual(order.phone, '11912345678')
        self.assertEqual(order.cep, '01234567')

    # --- Recusas -------------------------------------------------------------
    def test_estoque_insuficiente_nao_cria_nada(self):
        """Se o estoque acabar entre o carrinho e o checkout, nada é salvo."""
        self.add_to_cart(3)
        # Outra cliente comprou: sobrou só 1 (o carrinho ainda tem 3).
        self.variant.stock = 1
        self.variant.save()
        response = self.checkout()
        self.assertRedirects(response, reverse('cart_detail'))
        self.assertEqual(Order.objects.count(), 0)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 1)

    def test_carrinho_vazio_volta_ao_carrinho(self):
        response = self.client.get(reverse('checkout'))
        self.assertRedirects(response, reverse('cart_detail'))

    def test_dados_invalidos_mostram_erros(self):
        self.add_to_cart(1)
        data = dict(CUSTOMER_DATA, phone='1234', cep='123')
        response = self.checkout(data)
        self.assertEqual(response.status_code, 200)  # volta ao formulário
        self.assertContains(response, 'Informe o telefone com DDD')
        self.assertContains(response, 'O CEP deve ter 8 números')
        self.assertEqual(Order.objects.count(), 0)

    def test_cliente_nao_consegue_definir_status(self):
        """Campos fora do formulário (status) são ignorados no POST."""
        self.add_to_cart(1)
        self.checkout(dict(CUSTOMER_DATA, status='enviado'))
        self.assertEqual(Order.objects.get().status, Order.Status.NEW)

    def test_pagina_de_checkout_tem_aviso_lgpd(self):
        self.add_to_cart(1)
        response = self.client.get(reverse('checkout'))
        self.assertContains(response, 'Usamos seus dados apenas para')
        self.assertContains(response, reverse('privacy'))

    # --- Confirmação ---------------------------------------------------------
    def test_confirmacao_mostra_pedido_e_link_do_whatsapp(self):
        self.add_to_cart(1)
        self.checkout()
        order = Order.objects.get()
        response = self.client.get(reverse('order_confirmation'))
        self.assertContains(response, f'Pedido nº {order.pk} recebido!')
        self.assertContains(response, f'https://wa.me/{settings.WHATSAPP_NUMBER}?text=')

    def test_confirmacao_sem_pedido_na_sessao_redireciona(self):
        """Outro navegador não vê o pedido (nem o endereço) de ninguém."""
        response = self.client.get(reverse('order_confirmation'))
        self.assertRedirects(response, reverse('home'))


class CheckoutSecurityTest(TestCase):
    """Proteções do checkout: limite de pedidos por IP e token CSRF."""

    def setUp(self):
        cache.clear()  # zera o contador do limite (veja CheckoutTest.setUp)
        self.product = Product.objects.create(
            category=Category.objects.get(slug='vestidos'),
            name='Vestido Seguro', slug='vestido-seguro', price='100.00',
        )
        # Estoque folgado: aqui queremos testar o LIMITE, não a falta de peças.
        self.variant = ProductVariant.objects.create(product=self.product, size='M', stock=50)

    def add_to_cart(self, client, quantity=1):
        """Coloca peças no carrinho do "navegador" (client) informado."""
        client.post(
            reverse('cart_add', args=[self.product.id]),
            {'variant': self.variant.id, 'quantity': quantity},
        )

    def checkout(self, client):
        """Envia o formulário de checkout pelo client informado."""
        return client.post(reverse('checkout'), CUSTOMER_DATA)

    def make_orders(self, how_many):
        """Faz vários pedidos seguidos, como um robô faria."""
        for _ in range(how_many):
            self.add_to_cart(self.client)
            self.checkout(self.client)

    def test_limite_de_pedidos_por_ip(self):
        self.make_orders(MAX_ORDERS_PER_HOUR)
        self.assertEqual(Order.objects.count(), MAX_ORDERS_PER_HOUR)

        # O próximo pedido do mesmo IP é recusado com aviso...
        self.add_to_cart(self.client)
        stock_before = ProductVariant.objects.get(pk=self.variant.pk).stock
        response = self.checkout(self.client)
        self.assertContains(response, 'muitos pedidos deste aparelho')
        # ...e nada muda no banco: nem pedido novo, nem estoque.
        self.assertEqual(Order.objects.count(), MAX_ORDERS_PER_HOUR)
        self.assertEqual(ProductVariant.objects.get(pk=self.variant.pk).stock, stock_before)

    def test_outro_ip_continua_comprando(self):
        self.make_orders(MAX_ORDERS_PER_HOUR)
        # REMOTE_ADDR finge que a requisição veio de outro aparelho.
        other_client = Client(REMOTE_ADDR='10.0.0.2')
        self.add_to_cart(other_client)
        response = self.checkout(other_client)
        self.assertRedirects(response, reverse('order_confirmation'))
        self.assertEqual(Order.objects.count(), MAX_ORDERS_PER_HOUR + 1)

    def test_checkout_sem_token_csrf_e_recusado(self):
        # Nos testes, o Django normalmente "dispensa" o CSRF. Com
        # enforce_csrf_checks=True ele age como em produção: um POST vindo
        # de outro site (sem o token do formulário) recebe 403 Proibido.
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(reverse('checkout'), CUSTOMER_DATA)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Order.objects.exists())


class OrderStatusTest(TestCase):
    """Cancelar devolve o estoque; cancelado é final."""

    def setUp(self):
        product = Product.objects.create(
            category=Category.objects.get(slug='saias'),
            name='Saia Teste', slug='saia-teste', price='80.00',
        )
        # Situação depois de um pedido de 2 peças: estoque já descontado (5 -> 3).
        self.variant = ProductVariant.objects.create(product=product, size='P', stock=3)
        form = CheckoutForm(CUSTOMER_DATA)
        self.assertTrue(form.is_valid())
        self.order = form.save()
        OrderItem.objects.create(
            order=self.order, variant=self.variant, product_name='Saia Teste',
            size='P', unit_price='80.00', quantity=2,
        )

    def cancel(self):
        self.order.status = Order.Status.CANCELLED
        self.order.save()
        self.variant.refresh_from_db()

    def test_cancelar_devolve_o_estoque(self):
        self.cancel()
        self.assertEqual(self.variant.stock, 5)

    def test_salvar_cancelado_de_novo_nao_devolve_em_dobro(self):
        self.cancel()
        self.order.save()  # salvar outra vez, ainda cancelado
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)

    def test_outros_status_nao_mexem_no_estoque(self):
        self.order.status = Order.Status.SHIPPED
        self.order.save()
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 3)

    def test_cancelado_nao_pode_ser_reaberto(self):
        self.cancel()
        self.order.status = Order.Status.NEW
        with self.assertRaises(ValidationError):
            self.order.full_clean()  # validação usada pelo admin
        with self.assertRaises(ValidationError):
            self.order.save()  # e o save() também bloqueia
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)

    def test_variacao_apagada_nao_quebra_o_cancelamento(self):
        """O item fica no histórico (SET_NULL) e o cancelamento funciona."""
        self.variant.delete()
        self.order.status = Order.Status.CANCELLED
        self.order.save()
        self.assertEqual(self.order.items.get().product_name, 'Saia Teste')


class WhatsAppTest(TestCase):
    """Mensagem e link do WhatsApp."""

    def test_format_brl(self):
        self.assertEqual(format_brl(Decimal('1234.5')), 'R$ 1.234,50')
        self.assertEqual(format_brl(Decimal('99.9')), 'R$ 99,90')

    def test_link_tem_numero_e_mensagem_codificada(self):
        form = CheckoutForm(CUSTOMER_DATA)
        self.assertTrue(form.is_valid())
        order = form.save()
        OrderItem.objects.create(
            order=order, product_name='Vestido Helena', size='M',
            unit_price='229.90', quantity=2,
        )
        url = build_whatsapp_url(order)
        self.assertTrue(url.startswith(f'https://wa.me/{settings.WHATSAPP_NUMBER}?text='))
        # Codificado: sem espaços nem quebras de linha "crus" na URL.
        self.assertNotIn(' ', url)
        self.assertNotIn('\n', url)
        # Decodificando, a mensagem traz número do pedido, item, total e endereço.
        text = unquote(url.split('?text=')[1])
        self.assertIn(f'pedido nº {order.pk}', text)
        self.assertIn('Vestido Helena (tam. M) x2: R$ 459,80', text)
        self.assertIn('*Total:* R$ 459,80', text)
        self.assertIn('Rua das Flores, 100, Apto 12', text)
        self.assertIn('CEP 01234-567', text)
        self.assertIn('*Telefone:* (11) 91234-5678', text)


class OrderAdminTest(TestCase):
    """Painel de pedidos no admin."""

    def setUp(self):
        from django.contrib.auth.models import User
        admin_user = User.objects.create_superuser('dona', 'dona@example.com', 'senha-teste-123')
        self.client.force_login(admin_user)  # entra sem digitar senha (só em testes)
        product = Product.objects.create(
            category=Category.objects.get(slug='vestidos'),
            name='Vestido Admin', slug='vestido-admin', price='100.00',
        )
        self.variant = ProductVariant.objects.create(product=product, size='G', stock=0)
        form = CheckoutForm(CUSTOMER_DATA)
        self.assertTrue(form.is_valid())
        self.order = form.save()
        OrderItem.objects.create(
            order=self.order, variant=self.variant, product_name='Vestido Admin',
            size='G', unit_price='100.00', quantity=1,
        )

    def test_lista_e_detalhe_abrem(self):
        self.assertEqual(self.client.get(reverse('admin:pedidos_order_changelist')).status_code, 200)
        url = reverse('admin:pedidos_order_change', args=[self.order.pk])
        response = self.client.get(url)
        self.assertContains(response, 'Vestido Admin')  # itens visíveis no pedido

    def test_acao_cancelar_devolve_estoque(self):
        self.client.post(reverse('admin:pedidos_order_changelist'), {
            'action': 'cancel_orders',
            '_selected_action': [self.order.pk],
        })
        self.order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.variant.stock, 1)

    def test_pedido_novo_nao_pode_ser_apagado(self):
        url = reverse('admin:pedidos_order_delete', args=[self.order.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
