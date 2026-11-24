"""Testes de pedido: checkout, frete, status e transições, reserva de estoque,
"Meus pedidos" (IDOR), WhatsApp e admin.

v1 (etapa 7) + v2 Etapa 5. O gateway de pagamento ainda não existe: nos
testes, "pago" é marcado direto no model, como o webhook fará na Etapa 7.
"""

import io
from datetime import timedelta
from decimal import Decimal
from urllib.parse import unquote

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contas.test_utils import login_admin, make_customer, make_order, make_variant
from loja.models import StoreSettings

from .models import Order, OrderItem, ShippingRate, active_orders
from .rate_limit import MAX_ORDERS_PER_HOUR
from .reservations import cancel_order_by_customer, expire_order, expire_overdue_orders
from .shipping import ShippingUnavailableError, calculate_shipping
from .whatsapp import build_whatsapp_url, format_brl

S = Order.Status

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

# Valores PROVISÓRIOS que as migrations colocam no banco de testes
# (pedidos/0004 e loja/0004). Os testes usam estes números.
SP_SHIPPING = Decimal('19.90')
FREE_SHIPPING_FROM = Decimal('299.00')


class CheckoutTest(TestCase):
    """Do carrinho ao pedido salvo no banco, ligado à conta e com frete."""

    def setUp(self):
        # O contador do limite de pedidos fica no cache, que NÃO é apagado
        # entre um teste e outro (só o banco é). Limpamos para que pedidos
        # de um teste não contem no limite do próximo.
        cache.clear()
        self.variant = make_variant(price='150.00', stock=5)
        self.product = self.variant.product
        # O checkout exige conta com e-mail verificado (decisão 72).
        self.customer = make_customer(first_name='Maria', last_name='da Silva')
        self.client.force_login(self.customer)

    def add_to_cart(self, quantity=1):
        """Coloca peças no carrinho pelo mesmo formulário da página do produto."""
        self.client.post(
            reverse('cart_add', args=[self.product.id]),
            {'variant': self.variant.id, 'quantity': quantity},
        )

    def checkout(self, data=CUSTOMER_DATA):
        """Envia o formulário de checkout."""
        return self.client.post(reverse('checkout'), data)

    # --- Pedido criado -------------------------------------------------------
    def test_checkout_cria_pedido_da_conta_e_vai_para_o_detalhe(self):
        self.add_to_cart(1)
        response = self.checkout()
        order = Order.objects.get()
        self.assertRedirects(response, reverse('order_detail', args=[order.pk]))
        self.assertEqual(order.user, self.customer)
        self.assertEqual(order.status, S.AWAITING_PAYMENT)
        item = order.items.get()
        self.assertEqual((item.product_name, item.size, item.quantity), (self.product.name, 'M', 1))

    def test_reserva_usa_o_prazo_da_configuracao(self):
        config = StoreSettings.load()
        config.reservation_minutes = 10
        config.save()
        self.add_to_cart(1)
        self.checkout()
        expected = timezone.now() + timedelta(minutes=10)
        # delta: aceita alguns segundos de diferença (o tempo do próprio teste).
        self.assertAlmostEqual(Order.objects.get().expires_at, expected, delta=timedelta(seconds=10))

    def test_preco_fica_guardado_no_item(self):
        """Mudar o preço do produto depois NÃO muda o pedido já feito."""
        self.add_to_cart(1)
        self.checkout()
        self.product.price = Decimal('999.00')
        self.product.save()
        self.assertEqual(OrderItem.objects.get().unit_price, Decimal('150.00'))

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

    def test_nome_da_conta_ja_vem_preenchido(self):
        self.add_to_cart(1)
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.context['form'].initial['customer_name'], 'Maria da Silva')

    # --- Frete ---------------------------------------------------------------
    def test_frete_pela_uf(self):
        self.add_to_cart(1)  # R$ 150, abaixo do frete grátis
        self.checkout()
        order = Order.objects.get()
        self.assertEqual(order.shipping_cost, SP_SHIPPING)
        self.assertEqual(order.total, Decimal('150.00') + SP_SHIPPING)

    def test_frete_gratis_acima_do_limite(self):
        self.add_to_cart(2)  # R$ 300 >= R$ 299
        self.checkout()
        self.assertEqual(Order.objects.get().shipping_cost, Decimal('0'))

    def test_frete_gratis_vale_no_valor_exato_do_limite(self):
        config = StoreSettings.load()
        config.free_shipping_threshold = Decimal('150.00')
        config.save()
        self.add_to_cart(1)  # exatamente R$ 150
        self.checkout()
        self.assertEqual(Order.objects.get().shipping_cost, Decimal('0'))

    def test_uf_sem_frete_e_recusada_sem_gravar_nada(self):
        ShippingRate.objects.filter(state='AC').delete()
        self.add_to_cart(1)
        response = self.checkout(dict(CUSTOMER_DATA, state='AC'))
        self.assertEqual(response.status_code, 200)  # volta ao formulário
        self.assertContains(response, 'Ainda não entregamos neste estado')
        self.assertFalse(Order.objects.exists())
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)  # nada foi reservado

    def test_mudar_a_tabela_depois_nao_muda_o_pedido(self):
        self.add_to_cart(1)
        self.checkout()
        ShippingRate.objects.filter(state='SP').update(price=Decimal('99.00'))
        self.assertEqual(Order.objects.get().shipping_cost, SP_SHIPPING)

    def test_tabela_de_frete_vai_para_a_pagina(self):
        self.add_to_cart(1)
        response = self.client.get(reverse('checkout'))
        self.assertContains(response, 'id="tabela-frete"')  # json_script, para o JavaScript
        self.assertContains(response, 'Ver tabela de frete')  # lista, sem JavaScript

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
        response = self.checkout(dict(CUSTOMER_DATA, phone='1234', cep='123'))
        self.assertEqual(response.status_code, 200)  # volta ao formulário
        self.assertContains(response, 'Informe o telefone com DDD')
        self.assertContains(response, 'O CEP deve ter 8 números')
        self.assertEqual(Order.objects.count(), 0)

    def test_cliente_nao_consegue_definir_status_frete_nem_dona(self):
        """Campos fora do formulário são ignorados no POST."""
        other = make_customer(email='outra@example.com')
        self.add_to_cart(1)
        self.checkout(dict(CUSTOMER_DATA, status='pago', shipping_cost='0', user=other.pk))
        order = Order.objects.get()
        self.assertEqual(order.status, S.AWAITING_PAYMENT)
        self.assertEqual(order.shipping_cost, SP_SHIPPING)
        self.assertEqual(order.user, self.customer)

    def test_pagina_de_checkout_tem_aviso_lgpd(self):
        self.add_to_cart(1)
        response = self.client.get(reverse('checkout'))
        self.assertContains(response, 'Usamos seus dados apenas para')
        self.assertContains(response, reverse('privacy'))


class ShippingFunctionTest(TestCase):
    """calculate_shipping, sozinha."""

    def test_sem_limite_de_frete_gratis_sempre_cobra(self):
        config = StoreSettings.load()
        config.free_shipping_threshold = None
        config.save()
        self.assertEqual(calculate_shipping('SP', Decimal('5000.00')), SP_SHIPPING)

    def test_uf_sem_frete_lanca_erro(self):
        ShippingRate.objects.filter(state='RR').delete()
        with self.assertRaises(ShippingUnavailableError):
            calculate_shipping('RR', Decimal('10.00'))

    def test_migration_criou_as_27_ufs_provisorias(self):
        self.assertEqual(ShippingRate.objects.count(), 27)
        self.assertEqual(ShippingRate.objects.filter(is_provisional=False).count(), 0)
        self.assertEqual(StoreSettings.load().free_shipping_threshold, FREE_SHIPPING_FROM)


class CheckoutSecurityTest(TestCase):
    """Proteções do checkout: limite de pedidos por IP e token CSRF."""

    def setUp(self):
        cache.clear()  # zera o contador do limite (veja CheckoutTest.setUp)
        # Estoque folgado: aqui queremos testar o LIMITE, não a falta de peças.
        self.variant = make_variant(slug='vestido-seguro', price='100.00', stock=50)
        self.customer = make_customer()
        self.client.force_login(self.customer)

    def add_to_cart(self, client, quantity=1):
        """Coloca peças no carrinho do "navegador" (client) informado."""
        client.post(
            reverse('cart_add', args=[self.variant.product.id]),
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
        stock_before = self.variant.__class__.objects.get(pk=self.variant.pk).stock
        response = self.checkout(self.client)
        self.assertContains(response, 'muitos pedidos deste aparelho')
        # ...e nada muda no banco: nem pedido novo, nem estoque.
        self.assertEqual(Order.objects.count(), MAX_ORDERS_PER_HOUR)
        self.assertEqual(self.variant.__class__.objects.get(pk=self.variant.pk).stock, stock_before)

    def test_outro_ip_continua_comprando(self):
        self.make_orders(MAX_ORDERS_PER_HOUR)
        # REMOTE_ADDR finge que a requisição veio de outro aparelho.
        other_client = Client(REMOTE_ADDR='10.0.0.2')
        other_client.force_login(self.customer)
        self.add_to_cart(other_client)
        response = self.checkout(other_client)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), MAX_ORDERS_PER_HOUR + 1)

    def test_checkout_sem_token_csrf_e_recusado(self):
        # Nos testes, o Django normalmente "dispensa" o CSRF. Com
        # enforce_csrf_checks=True ele age como em produção: um POST vindo
        # de outro site (sem o token do formulário) recebe 403 Proibido.
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.customer)
        response = csrf_client.post(reverse('checkout'), CUSTOMER_DATA)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Order.objects.exists())


class OrderTransitionTest(TestCase):
    """Tabela de transições de status (decisão 87) e devolução do estoque."""

    def setUp(self):
        # Situação depois de um pedido de 2 peças: estoque já descontado (5 -> 3).
        self.variant = make_variant(slug='saia-teste', price='80.00', size='P', stock=3)

    def order_with(self, status):
        """Pedido de 2 peças já no status informado."""
        return make_order(status=status, variant=self.variant, quantity=2)

    def change(self, order, new_status):
        """Muda o status e relê o estoque."""
        order.status = new_status
        order.save()
        self.variant.refresh_from_db()

    def test_cada_transicao_da_tabela(self):
        """Percorre TODAS as combinações: permitidas salvam, as outras dão erro."""
        allowed = {
            (S.AWAITING_PAYMENT, S.PAID), (S.AWAITING_PAYMENT, S.EXPIRED),
            (S.AWAITING_PAYMENT, S.CANCELLED), (S.PAID, S.SHIPPED),
            (S.PAID, S.REFUNDED), (S.SHIPPED, S.DELIVERED),
            (S.SHIPPED, S.REFUNDED), (S.DELIVERED, S.REFUNDED),
        }
        for old in S.values:
            for new in S.values:
                if old == new:
                    continue
                # subTest: se uma combinação falhar, o teste mostra QUAL e continua as outras.
                with self.subTest(de=old, para=new):
                    order = self.order_with(old)
                    order.status = new
                    if (old, new) in allowed:
                        order.save()
                        self.assertEqual(Order.objects.get(pk=order.pk).status, new)
                    else:
                        with self.assertRaises(ValidationError):
                            order.save()
                        self.assertEqual(Order.objects.get(pk=order.pk).status, old)

    def test_clean_do_admin_tambem_recusa(self):
        order = self.order_with(S.CANCELLED)
        order.status = S.AWAITING_PAYMENT
        with self.assertRaises(ValidationError):
            order.full_clean()  # validação usada pelos formulários do admin

    def test_devolve_estoque_ao_expirar_cancelar_e_estornar_pago(self):
        for old, new in [(S.AWAITING_PAYMENT, S.EXPIRED), (S.AWAITING_PAYMENT, S.CANCELLED),
                         (S.PAID, S.REFUNDED)]:
            with self.subTest(de=old, para=new):
                self.variant.refresh_from_db()
                before = self.variant.stock
                self.change(self.order_with(old), new)
                self.assertEqual(self.variant.stock, before + 2)

    def test_nao_devolve_estoque_ao_pagar_enviar_ou_estornar_enviado(self):
        for old, new in [(S.AWAITING_PAYMENT, S.PAID), (S.PAID, S.SHIPPED), (S.SHIPPED, S.DELIVERED),
                         (S.SHIPPED, S.REFUNDED), (S.DELIVERED, S.REFUNDED)]:
            with self.subTest(de=old, para=new):
                self.variant.refresh_from_db()
                before = self.variant.stock
                self.change(self.order_with(old), new)
                self.assertEqual(self.variant.stock, before)

    def test_salvar_de_novo_nao_devolve_em_dobro(self):
        order = self.order_with(S.AWAITING_PAYMENT)
        self.change(order, S.CANCELLED)
        order.save()  # salvar outra vez, ainda cancelado
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)

    def test_enviado_grava_a_data_de_envio(self):
        order = self.order_with(S.PAID)
        self.change(order, S.SHIPPED)
        self.assertIsNotNone(Order.objects.get(pk=order.pk).shipped_at)

    def test_entregue_grava_a_data_de_entrega(self):
        order = self.order_with(S.SHIPPED)
        self.change(order, S.DELIVERED)
        self.assertIsNotNone(Order.objects.get(pk=order.pk).delivered_at)

    def test_variacao_apagada_nao_quebra_o_cancelamento(self):
        """O item fica no histórico (SET_NULL) e o cancelamento funciona."""
        order = self.order_with(S.AWAITING_PAYMENT)
        self.variant.delete()
        order.status = S.CANCELLED
        order.save()
        self.assertEqual(order.items.get().product_name, 'Produto saia-teste')


class ReservationExpiryTest(TestCase):
    """Expiração da reserva: comando, rede de segurança nas páginas e idempotência."""

    def setUp(self):
        # Estoque 0: as 2 peças estão reservadas pelo pedido abaixo.
        self.variant = make_variant(stock=0)
        self.customer = make_customer()
        self.past = timezone.now() - timedelta(minutes=1)
        self.overdue = make_order(
            user=self.customer, variant=self.variant, quantity=2, expires_at=self.past,
        )

    def stock(self):
        self.variant.refresh_from_db()
        return self.variant.stock

    def run_command(self, *args):
        out = io.StringIO()
        call_command('expirar_pedidos', *args, stdout=out)
        return out.getvalue()

    def test_comando_expira_e_devolve_o_estoque(self):
        output = self.run_command()
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.status, S.EXPIRED)
        self.assertEqual(self.stock(), 2)
        self.assertIn('Pedidos expirados (estoque devolvido): 1', output)
        self.assertNotIn('Maria', output)  # saída sem dado pessoal

    def test_rodar_duas_vezes_nao_devolve_em_dobro(self):
        self.run_command()
        self.run_command()
        self.assertEqual(self.stock(), 2)

    def test_dry_run_nao_altera_nada(self):
        output = self.run_command('--dry-run')
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.status, S.AWAITING_PAYMENT)
        self.assertEqual(self.stock(), 0)
        self.assertIn('seriam expirados: 1', output)

    def test_nao_mexe_em_pedido_no_prazo_pago_ou_sem_prazo(self):
        future = make_order(variant=self.variant, expires_at=timezone.now() + timedelta(minutes=10))
        paid = make_order(status=S.PAID, variant=self.variant, expires_at=self.past)
        legacy = make_order(variant=self.variant)  # pedido da v1: sem prazo
        self.assertEqual(expire_overdue_orders(), 1)  # só o vencido do setUp
        for order in (future, paid, legacy):
            order.refresh_from_db()
        self.assertEqual(future.status, S.AWAITING_PAYMENT)
        self.assertEqual(paid.status, S.PAID)
        self.assertEqual(legacy.status, S.AWAITING_PAYMENT)

    def test_pagamento_confirmado_antes_vence_a_corrida(self):
        """Simula a corrida: o pagamento chega entre a lista e a expiração.

        expire_order relê o pedido com trava e vê que não está mais
        "aguardando": não expira e não devolve o estoque.
        """
        self.overdue.status = S.PAID
        self.overdue.save()
        self.assertFalse(expire_order(self.overdue.pk, timezone.now()))
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.status, S.PAID)
        self.assertEqual(self.stock(), 0)

    def test_pagina_do_produto_expira_os_vencidos(self):
        """Rede de segurança: mesmo sem agendador, a peça volta ao abrir o produto."""
        response = self.client.get(self.variant.product.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.stock(), 2)

    def test_adicionar_ao_carrinho_expira_os_vencidos(self):
        """A peça "esgotada" pela reserva vencida pode ser comprada de novo."""
        other = Client()
        other.post(
            reverse('cart_add', args=[self.variant.product.id]),
            {'variant': self.variant.id, 'quantity': 1},
        )
        self.assertEqual(other.session.get('cart'), {str(self.variant.id): 1})

    def test_meus_pedidos_expira_os_vencidos_da_conta(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('my_orders'))
        self.assertContains(response, 'Expirado')
        self.assertEqual(self.stock(), 2)


class MyOrdersTest(TestCase):
    """ "Meus pedidos": cada cliente só vê os próprios (contra IDOR)."""

    def setUp(self):
        variant = make_variant(stock=10)
        self.maria = make_customer(email='maria@example.com')
        self.ana = make_customer(email='ana@example.com')
        self.order_maria = make_order(user=self.maria, variant=variant)
        self.order_ana = make_order(user=self.ana, variant=variant, customer_name='Ana Souza')
        self.order_v1 = make_order(user=None, variant=variant)  # pedido da v1, sem dona
        self.client.force_login(self.maria)

    def test_lista_so_os_pedidos_da_conta(self):
        response = self.client.get(reverse('my_orders'))
        self.assertEqual(list(response.context['orders']), [self.order_maria])

    def test_detalhe_do_proprio_pedido_abre(self):
        response = self.client.get(reverse('order_detail', args=[self.order_maria.pk]))
        self.assertContains(response, f'Pedido nº {self.order_maria.pk}')

    def test_pedido_de_outra_cliente_da_404(self):
        """Trocar o número na URL não mostra o pedido (nem o endereço) da Ana."""
        response = self.client.get(reverse('order_detail', args=[self.order_ana.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, 'Ana Souza', status_code=404)

    def test_pedido_sem_dona_e_numero_inexistente_tambem_dao_404(self):
        """A resposta é a mesma: ninguém descobre quais números existem."""
        for pk in (self.order_v1.pk, 999999):
            with self.subTest(pk=pk):
                response = self.client.get(reverse('order_detail', args=[pk]))
                self.assertEqual(response.status_code, 404)

    def test_visitante_vai_para_o_login(self):
        anonymous = Client()
        for url in (reverse('my_orders'), reverse('order_detail', args=[self.order_maria.pk])):
            with self.subTest(url=url):
                response = anonymous.get(url)
                self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_detalhe_mostra_reserva_e_link_do_whatsapp(self):
        self.order_maria.expires_at = timezone.now() + timedelta(minutes=30)
        self.order_maria.save()
        response = self.client.get(reverse('order_detail', args=[self.order_maria.pk]))
        self.assertContains(response, 'Suas peças estão reservadas até')
        self.assertContains(response, f'https://wa.me/{settings.WHATSAPP_NUMBER}?text=')


class CustomerCancelTest(TestCase):
    """A cliente cancela o próprio pedido aguardando pagamento (decisão 96).

    Atenção: os testes rodam no MySQL (banco temporário test_elegancia_crista),
    mas as requisições vão UMA DEPOIS DA OUTRA, na mesma conexão e dentro da
    transação do TestCase. Provam a lógica (clique duplo, status já mudado),
    mas NÃO provam a concorrência real de duas requisições simultâneas: um
    select_for_update() na mesma conexão nunca espera ninguém. A garantia
    contra devolução em dobro vem da trava do MySQL e só se confirma com duas
    conexões ao mesmo tempo (TransactionTestCase com threads, ou carga real).
    """

    def setUp(self):
        self.variant = make_variant(price='150.00', stock=3)
        self.maria = make_customer()
        self.other = make_customer(email='outra@example.com')
        self.order = make_order(user=self.maria, variant=self.variant, quantity=2)
        self.client.force_login(self.maria)

    def cancel(self, order):
        return self.client.post(reverse('cancel_order', args=[order.pk]))

    def test_cancela_e_devolve_o_estoque(self):
        response = self.cancel(self.order)
        self.assertRedirects(response, reverse('my_orders'))
        self.order.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(self.order.status, S.CANCELLED)
        self.assertEqual(self.variant.stock, 5)  # 3 + 2 devolvidas

    def test_so_aceita_post(self):
        response = self.client.get(reverse('cancel_order', args=[self.order.pk]))
        self.assertEqual(response.status_code, 405)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)

    def test_exige_login(self):
        self.client.logout()
        response = self.cancel(self.order)
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)

    def test_pedido_de_outra_conta_ou_sem_dona_da_404_e_nao_muda(self):
        others = [make_order(user=self.other, variant=self.variant),
                  make_order(user=None, variant=self.variant)]
        for order in others:
            with self.subTest(pedido=order.pk):
                self.assertEqual(self.cancel(order).status_code, 404)
                order.refresh_from_db()
                self.assertEqual(order.status, S.AWAITING_PAYMENT)
        self.assertEqual(self.client.post(reverse('cancel_order', args=[999999])).status_code, 404)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 3)

    def test_nao_cancela_pedido_que_nao_esta_aguardando(self):
        for status in (S.PAID, S.SHIPPED, S.DELIVERED, S.EXPIRED, S.REFUNDED):
            with self.subTest(status=status):
                order = make_order(user=self.maria, status=status, variant=self.variant)
                response = self.client.post(reverse('cancel_order', args=[order.pk]), follow=True)
                self.assertContains(response, 'não pode mais ser cancelado')
                order.refresh_from_db()
                self.assertEqual(order.status, status)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 3)

    def test_clique_duplo_nao_devolve_estoque_em_dobro(self):
        self.cancel(self.order)
        self.cancel(self.order)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)

    def test_pedido_vencido_vira_expirado_e_nao_cancelado(self):
        Order.objects.filter(pk=self.order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.cancel(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.EXPIRED)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)  # devolvido uma vez só

    def test_servico_filtra_pela_dona(self):
        self.assertFalse(cancel_order_by_customer(self.other, self.order.pk))
        self.assertTrue(cancel_order_by_customer(self.maria, self.order.pk))

    def test_botao_so_aparece_em_pedido_aguardando(self):
        paid = make_order(user=self.maria, status=S.PAID, variant=self.variant)
        page = self.client.get(reverse('my_orders'))
        self.assertContains(page, reverse('cancel_order', args=[self.order.pk]))
        self.assertNotContains(page, reverse('cancel_order', args=[paid.pk]))
        detail = self.client.get(reverse('order_detail', args=[paid.pk]))
        self.assertNotContains(detail, 'Cancelar pedido')


class ActiveOrdersTest(TestCase):
    """Definição de pedido "ativo" (decisão 92), usada para bloquear a exclusão da conta."""

    def setUp(self):
        self.variant = make_variant(stock=10)
        self.user = make_customer()

    def is_active(self, status, shipped_days_ago=None, delivered_days_ago=None):
        """Cria um pedido e diz se ele conta como ativo."""
        order = make_order(user=self.user, status=status, variant=self.variant)
        if delivered_days_ago is not None:
            Order.objects.filter(pk=order.pk).update(
                delivered_at=timezone.now() - timedelta(days=delivered_days_ago)
            )
        if shipped_days_ago is not None:
            Order.objects.filter(pk=order.pk).update(
                shipped_at=timezone.now() - timedelta(days=shipped_days_ago)
            )
        result = active_orders(self.user).filter(pk=order.pk).exists()
        order.items.all().delete()
        Order.objects.filter(pk=order.pk).delete()
        return result

    def test_ativos(self):
        self.assertTrue(self.is_active(S.AWAITING_PAYMENT))
        self.assertTrue(self.is_active(S.PAID))
        self.assertTrue(self.is_active(S.SHIPPED, shipped_days_ago=5))
        # Enviado conta como ativo SEM limite: só "entregue" encerra (decisão 95).
        self.assertTrue(self.is_active(S.SHIPPED, shipped_days_ago=90))
        self.assertTrue(self.is_active(S.DELIVERED, delivered_days_ago=5))

    def test_nao_ativos(self):
        self.assertFalse(self.is_active(S.EXPIRED))
        self.assertFalse(self.is_active(S.CANCELLED))
        self.assertFalse(self.is_active(S.REFUNDED))
        # O prazo de 30 dias conta da ENTREGA, não do envio.
        self.assertFalse(self.is_active(S.DELIVERED, delivered_days_ago=31, shipped_days_ago=40))


class WhatsAppTest(TestCase):
    """Formatação de dinheiro e link do WhatsApp."""

    def test_format_brl(self):
        self.assertEqual(format_brl(Decimal('1234.5')), 'R$ 1.234,50')
        self.assertEqual(format_brl(Decimal('99.9')), 'R$ 99,90')

    def test_link_leva_so_o_numero_do_pedido(self):
        order = make_order(variant=make_variant())
        url = build_whatsapp_url(order)
        self.assertTrue(url.startswith(f'https://wa.me/{settings.WHATSAPP_NUMBER}?text='))
        # Codificado: sem espaços "crus" na URL.
        self.assertNotIn(' ', url)
        text = unquote(url.split('?text=')[1])
        self.assertIn(f'pedido nº {order.pk}', text)
        # Nenhum dado pessoal na URL (decisão 91).
        self.assertNotIn('Rua das Flores', text)
        self.assertNotIn('Maria', text)


class OrderAdminTest(TestCase):
    """Painel de pedidos, frete e configuração no admin."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        admin_user = get_user_model().objects.create_superuser(
            email='dona@example.com', password='senha-teste-123',
        )
        # Entra sem digitar senha nem código 2FA (só em testes; ver contas/test_utils.py).
        login_admin(self.client, admin_user)
        self.variant = make_variant(stock=0)

    def run_action(self, action, *orders):
        """Executa uma ação em massa do admin nos pedidos informados."""
        return self.client.post(reverse('admin:pedidos_order_changelist'), {
            'action': action,
            '_selected_action': [order.pk for order in orders],
        }, follow=True)

    def test_lista_e_detalhe_abrem(self):
        order = make_order(variant=self.variant)
        self.assertEqual(self.client.get(reverse('admin:pedidos_order_changelist')).status_code, 200)
        response = self.client.get(reverse('admin:pedidos_order_change', args=[order.pk]))
        self.assertContains(response, 'Produto vestido-teste')  # itens visíveis no pedido

    def test_status_nao_e_editavel_e_nao_existe_acao_pago(self):
        """ "Pago" só vem do gateway: o admin não tem campo nem ação para isso."""
        order = make_order(variant=self.variant)
        response = self.client.get(reverse('admin:pedidos_order_change', args=[order.pk]))
        self.assertNotContains(response, 'name="status"')
        changelist = self.client.get(reverse('admin:pedidos_order_changelist'))
        actions = {name for name, _label in changelist.context['action_form'].fields['action'].choices}
        self.assertEqual(
            actions - {''},
            {'mark_shipped', 'mark_delivered', 'cancel_orders', 'restore_stock_action'},
        )

    def test_acao_cancelar_devolve_estoque_e_pula_pago(self):
        awaiting = make_order(variant=self.variant)
        paid = make_order(status=S.PAID, variant=self.variant)
        response = self.run_action('cancel_orders', awaiting, paid)
        awaiting.refresh_from_db()
        paid.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(awaiting.status, S.CANCELLED)
        self.assertEqual(paid.status, S.PAID)
        self.assertEqual(self.variant.stock, 1)
        self.assertContains(response, '1 pedido(s) pulado(s)')

    def test_acao_enviar_so_de_pago(self):
        awaiting = make_order(variant=self.variant)
        paid = make_order(status=S.PAID, variant=self.variant)
        self.run_action('mark_shipped', awaiting, paid)
        awaiting.refresh_from_db()
        paid.refresh_from_db()
        self.assertEqual(awaiting.status, S.AWAITING_PAYMENT)
        self.assertEqual(paid.status, S.SHIPPED)

    def test_acao_entregar_so_de_enviado(self):
        paid = make_order(status=S.PAID, variant=self.variant)
        shipped = make_order(status=S.SHIPPED, variant=self.variant)
        self.run_action('mark_delivered', paid, shipped)
        paid.refresh_from_db()
        shipped.refresh_from_db()
        self.assertEqual(paid.status, S.PAID)
        self.assertEqual(shipped.status, S.DELIVERED)
        self.assertIsNotNone(shipped.delivered_at)

    def test_devolver_estoque_manual_so_de_estorno_de_enviado_e_uma_vez(self):
        """Estoque 0; o pedido tem 1 peça. Só o estornado-que-foi-enviado é elegível."""
        for status in (S.SHIPPED, S.DELIVERED):
            with self.subTest(origem=status):
                self.variant.stock = 0
                self.variant.save()
                order = make_order(status=status, variant=self.variant)
                Order.objects.filter(pk=order.pk).update(shipped_at=timezone.now())
                order.refresh_from_db()
                order.status = S.REFUNDED
                order.save()
                self.variant.refresh_from_db()
                self.assertEqual(self.variant.stock, 0)  # o estorno não devolve sozinho
                order.refresh_from_db()
                self.assertIsNone(order.stock_restored_at)
                # 1ª execução devolve; a 2ª e a 3ª não duplicam.
                for _ in range(3):
                    self.run_action('restore_stock_action', order)
                self.variant.refresh_from_db()
                order.refresh_from_db()
                self.assertEqual(self.variant.stock, 1)
                self.assertIsNotNone(order.stock_restored_at)
                # Quem e quando ficam no histórico do pedido.
                self.assertEqual(LogEntry.objects.filter(
                    object_id=str(order.pk), change_message__contains='Estoque devolvido manualmente',
                ).count(), 1)

    def test_devolver_estoque_manual_pula_pedidos_nao_elegiveis(self):
        paid = make_order(status=S.PAID, variant=self.variant)
        shipped = make_order(status=S.SHIPPED, variant=self.variant)
        refunded_paid = make_order(status=S.PAID, variant=self.variant)
        refunded_paid.status = S.REFUNDED
        refunded_paid.save()  # pago -> estornado: o estoque já voltou sozinho (stock 1)
        response = self.run_action('restore_stock_action', paid, shipped, refunded_paid)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 1)  # nada foi devolvido de novo
        self.assertContains(response, '3 pedido(s) pulado(s)')

    def test_so_apaga_pedido_cancelado_ou_expirado(self):
        for status, expected in [(S.AWAITING_PAYMENT, 403), (S.PAID, 403), (S.SHIPPED, 403), (S.DELIVERED, 403),
                                 (S.CANCELLED, 200), (S.EXPIRED, 200)]:
            with self.subTest(status=status):
                order = make_order(status=status, variant=self.variant)
                url = reverse('admin:pedidos_order_delete', args=[order.pk])
                self.assertEqual(self.client.get(url).status_code, expected)

    def test_tabela_de_frete_avisa_valores_provisorios(self):
        response = self.client.get(reverse('admin:pedidos_shippingrate_changelist'), follow=True)
        self.assertContains(response, 'com frete PROVISÓRIO')

    def test_configuracao_da_loja_e_unica(self):
        """A migration já criou a linha: não dá para adicionar outra nem apagar."""
        self.assertEqual(self.client.get(reverse('admin:loja_storesettings_add')).status_code, 403)
        url = reverse('admin:loja_storesettings_delete', args=[1])
        self.assertEqual(self.client.get(url).status_code, 403)
        StoreSettings(reservation_minutes=15).save()  # save() força o id 1
        self.assertEqual(StoreSettings.objects.count(), 1)
