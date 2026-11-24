"""Testes do Pix (v2 Etapa 7a): cobrança, tela, prazos, IDOR e logs.

O Mercado Pago é SEMPRE simulado: unittest.mock.patch troca a função
pagamentos.gateway.create_pix_order por um "dublê" que devolve uma resposta
pronta. Nenhum teste faz chamada de rede (regra do CLAUDE.md).

@override_settings(MERCADOPAGO_ACCESS_TOKEN=...): finge que há um token no
.env só durante o teste. O valor é falso e nunca sai daqui.
"""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from contas.test_utils import make_customer, make_order, make_variant
from loja.models import StoreSettings
from pedidos.models import Order

from . import gateway
from .gateway import GatewayError, GatewayOrder
from .models import Payment
from .pix import ORDER_EXPIRY_MARGIN

S = Order.Status
FAKE_TOKEN = 'TEST-token-falso-so-para-testes'
FAKE_PIX_CODE = '00020126580014br.gov.bcb.pix0136codigo-de-teste5204000053039865406169.905802BR6304ABCD'
# Caminho da função simulada. Simulamos onde ela é USADA (o módulo gateway,
# chamado por pix.py como gateway.create_pix_order).
CREATE_PIX = 'pagamentos.gateway.create_pix_order'


def fake_charge(**changes):
    """Resposta simulada do Mercado Pago para um Pix recém-criado."""
    data = {
        'id': 'ORD01TESTE', 'status': 'action_required', 'status_detail': 'waiting_transfer',
        'external_reference': 'pagamento-1', 'total_amount': Decimal('169.90'),
        'payment_id': 'PAY01TESTE', 'pix_code': FAKE_PIX_CODE,
    }
    data.update(changes)
    return GatewayOrder(**data)


def make_pending_order(user, **fields):
    """Pedido aguardando pagamento: 1 peça de R$ 150 + frete de R$ 19,90, reservado por 30 min."""
    variant = make_variant(slug=f'peca-{Order.objects.count()}', price='150.00', stock=3)
    defaults = {
        'shipping_cost': Decimal('19.90'),
        'expires_at': timezone.now() + timedelta(minutes=30),
    }
    defaults.update(fields)
    return make_order(user=user, variant=variant, **defaults)


# ---------------------------------------------------------------------------
# Corpo da requisição e conversão de valores (sem rede nenhuma)
# ---------------------------------------------------------------------------

class GatewayBodyTest(TestCase):
    """O que mandamos ao Mercado Pago: valores em texto, prazo ISO 8601, sem CPF."""

    def build(self):
        return gateway.build_pix_order_body(
            reference='pagamento-7', amount=Decimal('169.9'),
            payer_email='cliente@example.com', expiration_minutes=30,
        )

    @override_settings(MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME='')
    def test_corpo_do_pix(self):
        body = self.build()
        self.assertEqual(body['total_amount'], '169.90')  # texto, 2 casas
        self.assertEqual(body['external_reference'], 'pagamento-7')
        payment = body['transactions']['payments'][0]
        self.assertEqual(payment['amount'], '169.90')
        self.assertEqual(payment['payment_method'], {'id': 'pix', 'type': 'bank_transfer'})
        self.assertEqual(payment['expiration_time'], 'PT30M')

    @override_settings(MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME='')
    def test_pagadora_so_com_email_sem_cpf(self):
        """Decisão 59: nada de CPF (identification), nem nome, nem endereço."""
        self.assertEqual(self.build()['payer'], {'email': 'cliente@example.com'})

    @override_settings(MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME='APRO')
    def test_nome_de_teste_so_quando_configurado(self):
        """No sandbox, "APRO" faz o Mercado Pago aprovar o Pix de teste sozinho."""
        self.assertEqual(self.build()['payer']['first_name'], 'APRO')

    def test_valor_float_e_recusado(self):
        with self.assertRaises(TypeError):
            gateway.format_amount(169.9)

    def test_valor_do_mercado_pago_vira_decimal(self):
        self.assertEqual(gateway.parse_amount('169.90'), Decimal('169.90'))
        self.assertIsNone(gateway.parse_amount(''))
        self.assertIsNone(gateway.parse_amount('abc'))

    def test_resposta_vira_gateway_order(self):
        """Lê o "copia e cola" de transactions.payments[0].payment_method.qr_code."""
        body = {
            'id': 'ORD1', 'status': 'action_required', 'status_detail': 'waiting_transfer',
            'external_reference': 'pagamento-7', 'total_amount': '169.90',
            'transactions': {'payments': [{'id': 'PAY1', 'payment_method': {'qr_code': 'abc'}}]},
        }
        charge = gateway._to_gateway_order(body)
        self.assertEqual((charge.id, charge.payment_id, charge.pix_code), ('ORD1', 'PAY1', 'abc'))
        self.assertEqual(charge.total_amount, Decimal('169.90'))

    @override_settings(MERCADOPAGO_ACCESS_TOKEN=FAKE_TOKEN)
    def test_erro_do_gateway_nao_vaza_token_nem_resposta(self):
        """HTTP 400 vira GatewayError genérico; o log tem só a operação e o código."""
        def refused(*args):
            return {'status': 400, 'response': {'message': 'detalhe interno', 'payer': 'cliente@example.com'}}

        with self.assertLogs('pagamentos', 'WARNING') as logs:
            with self.assertRaises(GatewayError):
                gateway._call('criar Pix', refused)
        text = ' '.join(logs.output)
        self.assertIn('HTTP 400', text)
        for secret in (FAKE_TOKEN, 'cliente@example.com', 'detalhe interno'):
            self.assertNotIn(secret, text)

    def test_falha_de_rede_vira_gateway_error(self):
        def offline(*args):
            raise ConnectionError('sem rede')

        with self.assertLogs('pagamentos', 'WARNING'):
            with self.assertRaises(GatewayError):
                gateway._call('criar Pix', offline)

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='')
    def test_sem_token_nao_chama_o_sdk(self):
        self.assertFalse(gateway.is_configured())
        with self.assertRaises(GatewayError):
            gateway._sdk()


# ---------------------------------------------------------------------------
# Gerar o Pix (botão "Pagar com Pix")
# ---------------------------------------------------------------------------

@override_settings(MERCADOPAGO_ACCESS_TOKEN=FAKE_TOKEN, MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME='')
class StartPixTest(TestCase):
    """Cria a cobrança, alinha os prazos e reaproveita a mesma cobrança."""

    def setUp(self):
        self.customer = make_customer()
        self.client.force_login(self.customer)
        self.order = make_pending_order(self.customer)

    def start(self, order=None):
        return self.client.post(reverse('start_pix', args=[(order or self.order).pk]))

    def test_cria_o_pix_e_abre_a_pagina_do_qr(self):
        with mock.patch(CREATE_PIX, return_value=fake_charge()) as create:
            response = self.start()
        self.assertRedirects(response, reverse('pix_page', args=[self.order.pk]))
        payment = Payment.objects.get()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.gateway_order_id, 'ORD01TESTE')
        self.assertEqual(payment.pix_code, FAKE_PIX_CODE)
        # O que foi mandado ao "Mercado Pago": total do pedido (itens + frete) em Decimal.
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs['amount'], Decimal('169.90'))
        self.assertEqual(kwargs['amount'], self.order.total)
        self.assertEqual(kwargs['reference'], f'pagamento-{payment.pk}')
        self.assertEqual(kwargs['payer_email'], self.customer.email)
        self.assertEqual(kwargs['idempotency_key'], payment.idempotency_key)

    def test_prazos_pix_antes_do_pedido(self):
        """Decisão 103: Pix em agora + 30 min; pedido em Pix + 2 min."""
        with mock.patch(CREATE_PIX, return_value=fake_charge()) as create:
            self.start()
        payment = Payment.objects.get()
        self.order.refresh_from_db()
        self.assertEqual(create.call_args.kwargs['expiration_minutes'], 30)
        self.assertAlmostEqual(
            payment.expires_at, timezone.now() + timedelta(minutes=30), delta=timedelta(seconds=10)
        )
        self.assertEqual(self.order.expires_at, payment.expires_at + ORDER_EXPIRY_MARGIN)

    def test_reserva_renovada_quando_estava_quase_vencendo(self):
        """Faltavam 3 minutos: ao gerar o Pix, a reserva volta a ter 30 (+2)."""
        self.order.expires_at = timezone.now() + timedelta(minutes=3)
        self.order.save()
        with mock.patch(CREATE_PIX, return_value=fake_charge()):
            self.start()
        self.order.refresh_from_db()
        self.assertGreater(self.order.expires_at, timezone.now() + timedelta(minutes=31))

    def test_prazo_do_pix_segue_a_configuracao_da_loja(self):
        config = StoreSettings.load()
        config.reservation_minutes = 45
        config.save()
        with mock.patch(CREATE_PIX, return_value=fake_charge()) as create:
            self.start()
        self.assertEqual(create.call_args.kwargs['expiration_minutes'], 45)

    def test_segundo_clique_reaproveita_o_pix(self):
        """Um Pix por pedido: o 2º clique não chama o Mercado Pago de novo."""
        with mock.patch(CREATE_PIX, return_value=fake_charge()) as create:
            self.start()
            response = self.start()
        self.assertRedirects(response, reverse('pix_page', args=[self.order.pk]))
        self.assertEqual(create.call_count, 1)
        self.assertEqual(Payment.objects.count(), 1)

    def test_falha_do_gateway_nao_estraga_nada_e_reusa_a_chave(self):
        """Erro de rede: pedido intacto; a nova tentativa manda a MESMA chave de idempotência."""
        old_expires_at = self.order.expires_at
        with mock.patch(CREATE_PIX, side_effect=GatewayError('falhou')) as create:
            response = self.start()
            self.start()
        self.assertRedirects(response, reverse('order_detail', args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)
        self.assertEqual(self.order.expires_at, old_expires_at)
        payment = Payment.objects.get()
        self.assertEqual(payment.status, Payment.Status.CREATING)
        first_key = create.call_args_list[0].kwargs['idempotency_key']
        second_key = create.call_args_list[1].kwargs['idempotency_key']
        self.assertEqual(first_key, second_key)
        # Agora o Mercado Pago responde: aproveita o mesmo Payment.
        with mock.patch(CREATE_PIX, return_value=fake_charge()):
            self.start()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_mensagem_de_erro_e_generica(self):
        with mock.patch(CREATE_PIX, side_effect=GatewayError('detalhe técnico')):
            response = self.start()
        response = self.client.get(response.url)
        self.assertContains(response, 'Não foi possível gerar o Pix agora')
        self.assertNotContains(response, 'detalhe técnico')

    def test_pedido_de_outra_conta_da_404(self):
        """IDOR: o número existe, mas é de outra cliente. Mesma resposta de inexistente."""
        other = make_pending_order(make_customer(email='outra@example.com'))
        with mock.patch(CREATE_PIX) as create:
            self.assertEqual(self.start(other).status_code, 404)
        create.assert_not_called()
        self.assertFalse(Payment.objects.exists())

    def test_pedido_da_v1_sem_dona_da_404(self):
        old_order = make_pending_order(None, expires_at=None)
        with mock.patch(CREATE_PIX) as create:
            self.assertEqual(self.start(old_order).status_code, 404)
        create.assert_not_called()

    def test_pedido_inexistente_da_404(self):
        with mock.patch(CREATE_PIX) as create:
            response = self.client.post(reverse('start_pix', args=[99999]))
        self.assertEqual(response.status_code, 404)
        create.assert_not_called()

    def test_pedido_que_nao_aguarda_pagamento_nao_gera_pix(self):
        for status in (S.CANCELLED, S.EXPIRED):
            order = make_pending_order(self.customer, status=status)
            with mock.patch(CREATE_PIX) as create:
                response = self.start(order)
            self.assertRedirects(response, reverse('order_detail', args=[order.pk]))
            create.assert_not_called()
        self.assertFalse(Payment.objects.exists())

    def test_pedido_vencido_expira_e_nao_gera_pix(self):
        self.order.expires_at = timezone.now() - timedelta(minutes=1)
        self.order.save()
        with mock.patch(CREATE_PIX) as create:
            self.start()
        create.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.EXPIRED)

    def test_gerar_pix_nao_marca_como_pago(self):
        """Mesmo com o "Mercado Pago" dizendo aprovado, só o webhook marca pago (7b)."""
        with mock.patch(CREATE_PIX, return_value=fake_charge(status='processed', status_detail='accredited')):
            self.start()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)
        self.assertEqual(Payment.objects.get().status, Payment.Status.PENDING)

    def test_get_nao_gera_pix(self):
        with mock.patch(CREATE_PIX) as create:
            response = self.client.get(reverse('start_pix', args=[self.order.pk]))
        self.assertEqual(response.status_code, 405)
        create.assert_not_called()

    def test_visitante_sem_login_vai_para_o_login(self):
        self.client.logout()
        with mock.patch(CREATE_PIX) as create:
            response = self.start()
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)
        create.assert_not_called()

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='')
    def test_sem_token_o_pagamento_fica_indisponivel(self):
        with mock.patch(CREATE_PIX) as create:
            self.start()
        create.assert_not_called()
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'pagamento online está indisponível')
        self.assertNotContains(response, reverse('start_pix', args=[self.order.pk]))

    def test_detalhe_do_pedido_mostra_o_botao(self):
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, reverse('start_pix', args=[self.order.pk]))
        self.assertContains(response, 'Pagar com Pix')

    def test_log_sem_dados_pessoais_nem_de_pagamento(self):
        with mock.patch(CREATE_PIX, return_value=fake_charge()):
            with self.assertLogs('pagamentos', 'INFO') as logs:
                self.start()
        text = ' '.join(logs.output)
        self.assertIn(f'pedido {self.order.pk}', text)
        for secret in (self.customer.email, FAKE_PIX_CODE, FAKE_TOKEN, '169.90'):
            self.assertNotIn(secret, text)


# ---------------------------------------------------------------------------
# Página do QR Code e consulta da situação
# ---------------------------------------------------------------------------

@override_settings(MERCADOPAGO_ACCESS_TOKEN=FAKE_TOKEN)
class PixPageTest(TestCase):
    """A página mostra o QR e o "copia e cola"; a consulta lê só o banco."""

    def setUp(self):
        self.customer = make_customer()
        self.client.force_login(self.customer)
        self.order = make_pending_order(self.customer)
        self.payment = Payment.objects.create(
            order=self.order, method=Payment.Method.PIX, status=Payment.Status.PENDING,
            amount=self.order.total, pix_code=FAKE_PIX_CODE, gateway_order_id='ORD01TESTE',
            expires_at=timezone.now() + timedelta(minutes=30),
        )

    def test_mostra_qr_e_copia_e_cola(self):
        response = self.client.get(reverse('pix_page', args=[self.order.pk]))
        self.assertContains(response, 'class="pix__qr"')
        self.assertContains(response, 'xmlns="http://www.w3.org/2000/svg"')  # o SVG do QR Code
        self.assertContains(response, FAKE_PIX_CODE)
        self.assertContains(response, 'R$ 169,90')  # formato brasileiro (LANGUAGE_CODE pt-br)
        self.assertContains(response, reverse('pix_status', args=[self.order.pk]))

    def test_detalhe_do_pedido_leva_ao_qr_existente(self):
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'Ver o QR Code do Pix')

    def test_pagina_de_outra_conta_da_404(self):
        self.client.force_login(make_customer(email='outra@example.com'))
        response = self.client.get(reverse('pix_page', args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_sem_pix_gerado_volta_ao_pedido(self):
        other_order = make_pending_order(self.customer)
        response = self.client.get(reverse('pix_page', args=[other_order.pk]))
        self.assertRedirects(response, reverse('order_detail', args=[other_order.pk]))

    def test_pedido_que_nao_aguarda_nao_mostra_qr(self):
        Order.objects.filter(pk=self.order.pk).update(status=S.CANCELLED)
        response = self.client.get(reverse('pix_page', args=[self.order.pk]))
        self.assertNotContains(response, 'class="pix__qr"')
        self.assertNotContains(response, FAKE_PIX_CODE)

    def test_situacao_em_json(self):
        response = self.client.get(reverse('pix_status', args=[self.order.pk]))
        self.assertEqual(response.json(), {'status': S.AWAITING_PAYMENT})
        # never_cache: o navegador não guarda a resposta.
        self.assertIn('no-cache', response.headers['Cache-Control'])

    def test_situacao_nao_fala_com_o_gateway_nem_paga(self):
        """A tela só LÊ o banco: consultar várias vezes nunca vira "pago"."""
        with mock.patch(CREATE_PIX) as create:
            for _ in range(3):
                self.client.get(reverse('pix_status', args=[self.order.pk]))
        create.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)

    def test_situacao_mostra_expirado_quando_vence(self):
        Order.objects.filter(pk=self.order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        response = self.client.get(reverse('pix_status', args=[self.order.pk]))
        self.assertEqual(response.json(), {'status': S.EXPIRED})

    def test_situacao_de_outra_conta_da_404(self):
        self.client.force_login(make_customer(email='outra@example.com'))
        response = self.client.get(reverse('pix_status', args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_situacao_so_aceita_get(self):
        response = self.client.post(reverse('pix_status', args=[self.order.pk]))
        self.assertEqual(response.status_code, 405)


class ReservationMinimumTest(TestCase):
    """Decisão 103: a reserva (e o Pix) não pode ter menos de 30 minutos."""

    def test_menos_de_30_minutos_e_recusado(self):
        config = StoreSettings.load()
        config.reservation_minutes = 10
        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_30_minutos_e_aceito(self):
        config = StoreSettings.load()
        config.reservation_minutes = 30
        config.full_clean()  # não lança erro
