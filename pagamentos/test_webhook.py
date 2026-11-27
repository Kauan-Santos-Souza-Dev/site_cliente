"""Testes do webhook do Pix e do cancelamento no Mercado Pago (v2 Etapa 7b).

O Mercado Pago é SEMPRE simulado (sem rede), em duas camadas:
- Na maioria dos testes, mock.patch troca pagamentos.gateway.get_order por
  um "dublê" que devolve um GatewayOrder pronto.
- Em GatewaySdkCallTest, simulamos só requests.Session.request, a ÚLTIMA
  peça antes da internet. Assim o SDK de verdade roda (RequestOptions,
  montagem da URL e dos cabeçalhos) e um erro de tipo, como o
  connection_timeout int da 7a, aparece no teste.

A assinatura NÃO é simulada: os testes calculam o HMAC com uma chave falsa
(sign()) e quem confere é o validador real do SDK.
"""

import hashlib
import hmac
import json
import threading
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from contas.test_utils import make_customer, make_order, make_variant
from loja.models import Category
from pedidos.models import Order
from pedidos.reservations import expire_overdue_orders

from . import gateway, webhook
from .gateway import GatewayError, GatewayOrder
from .models import Payment

S = Order.Status
P = Payment.Status
FAKE_TOKEN = 'TEST-token-falso-so-para-testes'
FAKE_SECRET = 'chave-secreta-falsa-so-para-testes'
ORDER_ID = 'ORD01WEBHOOKTESTE'
GET_ORDER = 'pagamentos.gateway.get_order'
CANCEL_ORDER = 'pagamentos.gateway.cancel_order'

configured = override_settings(MERCADOPAGO_ACCESS_TOKEN=FAKE_TOKEN, MERCADOPAGO_WEBHOOK_SECRET=FAKE_SECRET)


def sign(data_id, request_id='req-123', ts='1764190000', secret=FAKE_SECRET):
    """Monta o cabeçalho x-signature como o Mercado Pago faz.

    Manifesto "id:<data.id>;request-id:<x-request-id>;ts:<ts>;" assinado com
    HMAC-SHA256 e a chave secreta. Resultado: "ts=<ts>,v1=<hex>".
    """
    manifest = f'id:{data_id};request-id:{request_id};ts:{ts};'
    digest = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f'ts={ts},v1={digest}'


def make_pix_payment(order, **fields):
    """Payment de Pix já criado no "Mercado Pago" e aguardando pagamento."""
    data = {
        'order': order, 'method': Payment.Method.PIX, 'status': P.PENDING,
        'amount': order.total, 'gateway_order_id': ORDER_ID, 'pix_code': 'copia-e-cola',
        'expires_at': timezone.now() + timedelta(minutes=30),
    }
    data.update(fields)
    return Payment.objects.create(**data)


def gateway_order(payment, **changes):
    """Resposta simulada do GET /v1/orders/{id}: por padrão, PAGA e com valor certo."""
    data = {
        'id': payment.gateway_order_id, 'status': 'processed', 'status_detail': 'accredited',
        'external_reference': payment.external_reference,
        'total_amount': payment.amount, 'total_paid_amount': payment.amount,
        'payment_id': 'PAY01TESTE', 'pix_code': '', 'qr_code_base64': '',
    }
    data.update(changes)
    return GatewayOrder(**data)


def make_pending_order(user, stock=3):
    """Pedido aguardando: 1 peça de R$ 150 + frete R$ 19,90 = R$ 169,90."""
    variant = make_variant(slug=f'peca-{Order.objects.count()}', price='150.00', stock=stock)
    order = make_order(
        user=user, variant=variant, shipping_cost=Decimal('19.90'),
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    return order, variant


class WebhookTestMixin:
    """Atalhos comuns: criar pedido + Pix e mandar um aviso assinado."""

    def setUp(self):
        self.customer = make_customer()
        self.order, self.variant = make_pending_order(self.customer)
        self.payment = make_pix_payment(self.order)

    def notify(self, data_id=ORDER_ID, signature=None, request_id='req-123', notification_type='order', client=None):
        """POST do aviso como o Mercado Pago manda: data.id e type na query, assinatura no cabeçalho."""
        query = f'?data.id={data_id}'
        if notification_type:
            query += f'&type={notification_type}'
        headers = {'HTTP_X_REQUEST_ID': request_id}
        signature = sign(data_id, request_id) if signature is None else signature
        if signature:
            headers['HTTP_X_SIGNATURE'] = signature
        # O corpo imita o do Mercado Pago, mas a view NEM o lê.
        body = json.dumps({'action': 'order.processed', 'data': {'id': data_id, 'status': 'processed'}})
        return (client or self.client).post(
            reverse('mercadopago_webhook') + query, data=body, content_type='application/json', **headers,
        )

    def refresh(self):
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.variant.refresh_from_db()


# ---------------------------------------------------------------------------
# Assinatura e regras da rota
# ---------------------------------------------------------------------------

@configured
class WebhookSignatureTest(WebhookTestMixin, TestCase):
    """Só aviso com assinatura válida é processado; o resto dá 401 e não muda nada."""

    def assert_nothing_changed(self):
        self.refresh()
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)
        self.assertEqual(self.payment.status, P.PENDING)

    def test_assinatura_valida_marca_como_pago(self):
        with mock.patch(GET_ORDER, return_value=gateway_order(self.payment)) as get_order:
            response = self.notify()
        self.assertEqual(response.status_code, 200)
        get_order.assert_called_once_with(ORDER_ID)
        self.refresh()
        self.assertEqual(self.order.status, S.PAID)
        self.assertEqual(self.payment.status, P.APPROVED)
        self.assertIsNotNone(self.payment.approved_at)

    def test_assinatura_invalida_da_401(self):
        with mock.patch(GET_ORDER) as get_order:
            response = self.notify(signature=sign(ORDER_ID, secret='chave-errada'))
        self.assertEqual(response.status_code, 401)
        get_order.assert_not_called()
        self.assert_nothing_changed()

    def test_sem_assinatura_da_401(self):
        with mock.patch(GET_ORDER) as get_order:
            response = self.notify(signature='')
        self.assertEqual(response.status_code, 401)
        get_order.assert_not_called()

    def test_assinatura_malformada_da_401(self):
        with mock.patch(GET_ORDER) as get_order:
            response = self.notify(signature='qualquer-coisa')
        self.assertEqual(response.status_code, 401)
        get_order.assert_not_called()

    def test_assinatura_de_outro_data_id_da_401(self):
        """Reaproveitar a assinatura de um aviso verdadeiro para outra order não funciona."""
        with mock.patch(GET_ORDER) as get_order:
            response = self.notify(signature=sign('ORD01OUTRA'))
        self.assertEqual(response.status_code, 401)
        get_order.assert_not_called()

    def test_x_request_id_trocado_da_401(self):
        with mock.patch(GET_ORDER) as get_order:
            response = self.notify(signature=sign(ORDER_ID, 'req-original'), request_id='req-trocado')
        self.assertEqual(response.status_code, 401)
        get_order.assert_not_called()

    def test_sem_data_id_da_401(self):
        with mock.patch(GET_ORDER) as get_order:
            response = self.notify(data_id='', signature=sign(''))
        self.assertEqual(response.status_code, 401)
        get_order.assert_not_called()

    def test_data_id_assinado_em_minusculas_tambem_vale(self):
        """Decisão 106: se a assinatura foi feita com o ID em minúsculas, também aceita."""
        with mock.patch(GET_ORDER, return_value=gateway_order(self.payment)):
            response = self.notify(signature=sign(ORDER_ID.lower()))
        self.assertEqual(response.status_code, 200)
        self.refresh()
        self.assertEqual(self.order.status, S.PAID)

    def test_log_temporario_diz_qual_tentativa_bateu(self):
        """Decisão 106: o log diz só "original" ou "minúscula" (sem ID, chave ou assinatura).

        Este teste sai junto com o log temporário, depois do teste no sandbox.
        """
        cases = [(sign(ORDER_ID), 'ID original'), (sign(ORDER_ID.lower()), 'ID minúscula')]
        for signature, expected in cases:
            with self.subTest(expected=expected):
                with mock.patch(GET_ORDER, return_value=gateway_order(self.payment)):
                    with self.assertLogs('pagamentos', 'INFO') as logs:
                        self.notify(signature=signature)
                text = ' '.join(logs.output)
                self.assertIn(f'assinatura conferida com o {expected}', text)
                for secret in (FAKE_SECRET, ORDER_ID, ORDER_ID.lower(), signature):
                    self.assertNotIn(secret, text)

    def test_assinatura_recusada_nao_gera_log_de_acerto(self):
        with self.assertLogs('pagamentos', 'INFO') as logs:
            self.notify(signature=sign(ORDER_ID, secret='chave-errada'))
        self.assertNotIn('assinatura conferida', ' '.join(logs.output))

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='')
    def test_sem_chave_no_env_da_503_e_nao_processa(self):
        """Problema de configuração NOSSO: 503 faz o Mercado Pago tentar de novo depois."""
        with mock.patch(GET_ORDER) as get_order:
            with self.assertLogs('pagamentos', 'ERROR'):
                response = self.notify()
        self.assertEqual(response.status_code, 503)
        get_order.assert_not_called()
        self.assert_nothing_changed()

    def test_so_aceita_post(self):
        response = self.client.get(reverse('mercadopago_webhook') + f'?data.id={ORDER_ID}')
        self.assertEqual(response.status_code, 405)

    def test_sem_login_e_sem_token_csrf(self):
        """O Mercado Pago não tem sessão nem token CSRF: a rota é isenta (protegida pela assinatura)."""
        client = Client(enforce_csrf_checks=True)
        with mock.patch(GET_ORDER, return_value=gateway_order(self.payment)):
            response = self.notify(client=client)
        self.assertEqual(response.status_code, 200)

    def test_tipo_de_aviso_que_nao_interessa_da_200_sem_consultar(self):
        with mock.patch(GET_ORDER) as get_order:
            response = self.notify(notification_type='payment')
        self.assertEqual(response.status_code, 200)
        get_order.assert_not_called()
        self.assert_nothing_changed()

    def test_tipo_orders_no_plural_tambem_vale(self):
        with mock.patch(GET_ORDER, return_value=gateway_order(self.payment)):
            self.notify(notification_type='orders')
        self.refresh()
        self.assertEqual(self.order.status, S.PAID)

    def test_order_desconhecida_da_200_sem_consultar(self):
        with mock.patch(GET_ORDER) as get_order:
            response = self.notify(data_id='ORD01NAOEXISTE')
        self.assertEqual(response.status_code, 200)
        get_order.assert_not_called()
        self.assert_nothing_changed()

    def test_mercado_pago_fora_do_ar_da_503(self):
        """Não deu para reconsultar: 503, nada muda, e o Mercado Pago reenvia depois."""
        with mock.patch(GET_ORDER, side_effect=GatewayError('falhou')):
            response = self.notify()
        self.assertEqual(response.status_code, 503)
        self.assert_nothing_changed()

    def test_corpo_do_aviso_e_ignorado(self):
        """O corpo diz "pago", mas o Mercado Pago (reconsultado) diz pendente: vale a reconsulta."""
        pending = gateway_order(self.payment, status='action_required', status_detail='waiting_transfer')
        with mock.patch(GET_ORDER, return_value=pending):
            response = self.notify()
        self.assertEqual(response.status_code, 200)
        self.assert_nothing_changed()

    def test_log_sem_segredos_nem_dados_pessoais(self):
        with mock.patch(GET_ORDER, return_value=gateway_order(self.payment)):
            with self.assertLogs('pagamentos', 'INFO') as logs:
                self.notify()
                self.notify(signature=sign(ORDER_ID, secret='chave-errada'))
        text = ' '.join(logs.output)
        self.assertIn('SignatureMismatch', text)
        for secret in (FAKE_SECRET, FAKE_TOKEN, self.customer.email, '169.90', ORDER_ID, sign(ORDER_ID)):
            self.assertNotIn(secret, text)


# ---------------------------------------------------------------------------
# O que acontece com o pedido (regra de webhook.py)
# ---------------------------------------------------------------------------

@configured
class WebhookOrderRulesTest(WebhookTestMixin, TestCase):
    """Pago, repetido, divergente, pendente, tardio e reserva definitiva."""

    def process(self, **changes):
        with mock.patch(GET_ORDER, return_value=gateway_order(self.payment, **changes)):
            result = webhook.process_order_notification(ORDER_ID)
        self.refresh()
        return result

    def test_pago_nao_mexe_no_estoque(self):
        """A peça já foi descontada no checkout: pagar não desconta de novo."""
        self.assertEqual(self.process(), webhook.PAID)
        self.assertEqual(self.variant.stock, 3)
        self.assertEqual(self.payment.gateway_status, 'processed')
        self.assertEqual(self.payment.gateway_status_detail, 'accredited')

    def test_aviso_repetido_nao_duplica_nada(self):
        self.assertEqual(self.process(), webhook.PAID)
        first_approved_at = self.payment.approved_at
        first_updated_at = self.payment.updated_at
        for _ in range(2):
            self.assertEqual(self.process(), webhook.REPEATED)
        self.assertEqual(self.order.status, S.PAID)
        self.assertEqual(self.payment.approved_at, first_approved_at)
        self.assertEqual(self.payment.updated_at, first_updated_at)
        self.assertEqual(self.variant.stock, 3)

    def test_aviso_repetido_pela_rota_responde_200(self):
        with mock.patch(GET_ORDER, return_value=gateway_order(self.payment)):
            responses = [self.notify().status_code for _ in range(3)]
        self.assertEqual(responses, [200, 200, 200])
        self.refresh()
        self.assertEqual(self.order.status, S.PAID)

    def test_valor_total_divergente(self):
        result = self.process(total_amount=Decimal('1.00'), total_paid_amount=Decimal('1.00'))
        self.assertEqual(result, webhook.DIVERGENT)
        self.assertEqual(self.payment.status, P.DIVERGENT)
        self.assertIsNone(self.payment.approved_at)
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)

    def test_valor_pago_menor_que_o_total(self):
        self.assertEqual(self.process(total_paid_amount=Decimal('169.89')), webhook.DIVERGENT)
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)

    def test_valor_pago_ausente_e_divergente(self):
        """Sem saber quanto foi pago, não confirma."""
        self.assertEqual(self.process(total_paid_amount=None), webhook.DIVERGENT)

    def test_total_do_pedido_mudou_depois_do_pix(self):
        """O valor congelado no Payment não bate mais com o pedido: não confirma."""
        Order.objects.filter(pk=self.order.pk).update(shipping_cost=Decimal('0.00'))
        self.assertEqual(self.process(), webhook.DIVERGENT)
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)

    def test_external_reference_de_outra_cobranca(self):
        self.assertEqual(self.process(external_reference='pagamento-999'), webhook.DIVERGENT)
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)

    def test_id_da_order_diferente(self):
        self.assertEqual(self.process(id='ORD01OUTRA'), webhook.DIVERGENT)

    def test_divergente_e_final_aviso_seguinte_nao_muda(self):
        self.process(total_paid_amount=Decimal('1.00'))
        self.assertEqual(self.process(), webhook.REPEATED)
        self.assertEqual(self.payment.status, P.DIVERGENT)
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)

    def test_pendente_nao_muda_nada(self):
        result = self.process(status='action_required', status_detail='waiting_transfer')
        self.assertEqual(result, webhook.NOT_PAID)
        self.assertEqual(self.payment.status, P.PENDING)
        self.assertEqual(self.payment.gateway_status_detail, 'waiting_transfer')
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)

    def test_nao_pago_com_valor_diferente_nunca_vira_divergente(self):
        """Ajuste 1: primeiro "está pago?"; só depois vínculo e valor."""
        cases = [
            {'status': 'action_required', 'status_detail': 'waiting_transfer'},
            {'status': 'canceled', 'status_detail': 'canceled'},
            {'status': 'failed', 'status_detail': 'expired'},
        ]
        for case in cases:
            with self.subTest(**case):
                Payment.objects.filter(pk=self.payment.pk).update(status=P.PENDING)
                result = self.process(
                    total_amount=Decimal('1.00'), total_paid_amount=None,
                    external_reference='pagamento-999', **case,
                )
                self.assertEqual(result, webhook.NOT_PAID)
                self.assertNotEqual(self.payment.status, P.DIVERGENT)

    def test_cancelada_ou_expirada_no_mercado_pago(self):
        """A order morreu no gateway: o Payment acompanha; o pedido segue a expiração local."""
        self.assertEqual(self.process(status='canceled', status_detail='expired'), webhook.NOT_PAID)
        self.assertEqual(self.payment.status, P.CANCELLED)
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)
        Payment.objects.filter(pk=self.payment.pk).update(status=P.PENDING)
        self.process(status='failed', status_detail='expired')
        self.assertEqual(self.payment.status, P.EXPIRED)

    def test_processed_com_reembolso_parcial_nao_e_pago(self):
        """"processed" sozinho não basta: precisa do "accredited"."""
        self.assertEqual(self.process(status_detail='partially_refunded'), webhook.NOT_PAID)
        self.assertEqual(self.order.status, S.AWAITING_PAYMENT)

    def test_pago_com_prazo_vencido_ainda_aguardando_vira_pago(self):
        """O comando não rodou a tempo: o Pix foi aceito na validade, então vale."""
        Order.objects.filter(pk=self.order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.process(), webhook.PAID)
        self.assertEqual(self.order.status, S.PAID)

    def test_reserva_vira_definitiva(self):
        """Depois de pago, o expirar_pedidos não devolve mais as peças."""
        self.process()
        Order.objects.filter(pk=self.order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(expire_overdue_orders(), 0)
        self.refresh()
        self.assertEqual(self.order.status, S.PAID)
        self.assertEqual(self.variant.stock, 3)

    def test_pagamento_tardio_pedido_expirado(self):
        """Opção B: o pedido não volta e o estoque não mexe; a dona decide."""
        self.order.status = S.EXPIRED
        self.order.save()  # devolve 1 peça: estoque 3 -> 4
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 4)
        with self.assertLogs('pagamentos', 'WARNING'):
            result = self.process()
        self.assertEqual(result, webhook.LATE)
        self.assertEqual(self.order.status, S.EXPIRED)
        self.assertEqual(self.payment.status, P.LATE_PAID)
        self.assertIsNotNone(self.payment.approved_at)
        self.assertEqual(self.variant.stock, 4)
        self.assertEqual(self.process(), webhook.REPEATED)

    def test_pagamento_tardio_pedido_cancelado_com_pix_cancelado(self):
        """A cliente cancelou (Pix cancelado no gateway), mas pagou mesmo assim."""
        self.order.status = S.CANCELLED
        self.order.save()
        Payment.objects.filter(pk=self.payment.pk).update(status=P.CANCELLED)
        self.assertEqual(self.process(), webhook.LATE)
        self.assertEqual(self.order.status, S.CANCELLED)
        self.assertEqual(self.payment.status, P.LATE_PAID)


# ---------------------------------------------------------------------------
# Cancelamento do Pix quando a cliente cancela o pedido (decisão 109)
# ---------------------------------------------------------------------------

@configured
class CancelPixChargeTest(WebhookTestMixin, TestCase):
    """Cancelar o pedido também cancela o Pix no Mercado Pago (melhor esforço)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.customer)

    def cancel(self):
        return self.client.post(reverse('cancel_order', args=[self.order.pk]))

    def test_cancela_o_pix_no_mercado_pago(self):
        closed = gateway_order(self.payment, status='canceled', status_detail='canceled')
        with mock.patch(CANCEL_ORDER, return_value=closed) as cancel_order:
            self.cancel()
        cancel_order.assert_called_once_with(ORDER_ID)
        self.refresh()
        self.assertEqual(self.order.status, S.CANCELLED)
        self.assertEqual(self.payment.status, P.CANCELLED)
        self.assertEqual(self.variant.stock, 4)

    def test_falha_do_gateway_nao_desfaz_o_cancelamento(self):
        with mock.patch(CANCEL_ORDER, side_effect=GatewayError('falhou')):
            with self.assertLogs('pagamentos', 'WARNING'):
                response = self.cancel()
        self.assertRedirects(response, reverse('my_orders'))
        self.refresh()
        self.assertEqual(self.order.status, S.CANCELLED)
        self.assertEqual(self.variant.stock, 4)
        self.assertEqual(self.payment.status, P.PENDING)

    def test_sem_pix_gerado_nao_chama_o_gateway(self):
        other_order, _variant = make_pending_order(self.customer)
        with mock.patch(CANCEL_ORDER) as cancel_order:
            self.client.post(reverse('cancel_order', args=[other_order.pk]))
        cancel_order.assert_not_called()
        other_order.refresh_from_db()
        self.assertEqual(other_order.status, S.CANCELLED)

    def test_pedido_que_nao_pode_ser_cancelado_nao_chama_o_gateway(self):
        Order.objects.filter(pk=self.order.pk).update(status=S.PAID)
        with mock.patch(CANCEL_ORDER) as cancel_order:
            self.cancel()
        cancel_order.assert_not_called()

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='')
    def test_sem_token_cancela_so_o_pedido(self):
        with mock.patch(CANCEL_ORDER) as cancel_order:
            self.cancel()
        cancel_order.assert_not_called()
        self.refresh()
        self.assertEqual(self.order.status, S.CANCELLED)


# ---------------------------------------------------------------------------
# Chamadas reais do SDK, com só a rede simulada
# ---------------------------------------------------------------------------

class FakeHttpResponse:
    """Imita o objeto de resposta do requests (o que o SDK lê)."""

    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.content = json.dumps(body).encode()

    def json(self):
        return self._body


@configured
class GatewaySdkCallTest(TestCase):
    """get_order e cancel_order passam pelo SDK real; só requests.Session.request é falso."""

    ORDER_BODY = {
        'id': ORDER_ID, 'status': 'processed', 'status_detail': 'accredited',
        'external_reference': 'pagamento-1', 'total_amount': '169.90', 'total_paid_amount': '169.90',
        'transactions': {'payments': [{'id': 'PAY01', 'status': 'processed'}]},
    }

    def call(self, function, status_code=200):
        with mock.patch('requests.Session.request', return_value=FakeHttpResponse(status_code, self.ORDER_BODY)) as request:
            result = function(ORDER_ID)
        return result, request

    def test_get_order_consulta_a_order_com_timeout_float(self):
        charge, request = self.call(gateway.get_order)
        method, url = request.call_args.args
        kwargs = request.call_args.kwargs
        self.assertEqual(method, 'GET')
        self.assertTrue(url.endswith(f'/v1/orders/{ORDER_ID}'))
        self.assertEqual(kwargs['timeout'], 10.0)
        self.assertIn(FAKE_TOKEN, kwargs['headers']['Authorization'])
        # Valores em Decimal, prontos para comparar com o pedido.
        self.assertEqual(charge.total_paid_amount, Decimal('169.90'))
        self.assertTrue(gateway.is_paid(charge))

    def test_cancel_order_usa_post_e_chave_de_idempotencia_nova(self):
        _charge, request = self.call(gateway.cancel_order)
        first_key = request.call_args.kwargs['headers']['x-idempotency-key']
        _charge, request = self.call(gateway.cancel_order)
        method, url = request.call_args.args
        self.assertEqual(method, 'POST')
        self.assertTrue(url.endswith(f'/v1/orders/{ORDER_ID}/cancel'))
        self.assertNotEqual(request.call_args.kwargs['headers']['x-idempotency-key'], first_key)

    def test_order_inexistente_vira_gateway_error(self):
        with self.assertLogs('pagamentos', 'WARNING'):
            with self.assertRaises(GatewayError):
                self.call(gateway.get_order, status_code=404)

    def test_cancelamento_recusado_vira_gateway_error(self):
        """409: a order já foi paga ou cancelada."""
        with self.assertLogs('pagamentos', 'WARNING'):
            with self.assertRaises(GatewayError):
                self.call(gateway.cancel_order, status_code=409)


# ---------------------------------------------------------------------------
# Dois avisos ao mesmo tempo (concorrência real, duas conexões ao MySQL)
# ---------------------------------------------------------------------------

@configured
class WebhookConcurrencyTest(TransactionTestCase):
    """Dois avisos iguais chegando juntos: só um confirma.

    Por que TransactionTestCase? O TestCase comum roda tudo dentro de UMA
    transação, numa conexão só, e um select_for_update() nunca espera
    ninguém (veja pedidos/tests.py, CustomerCancelTest). Aqui cada thread tem
    a SUA conexão com o MySQL, e as transações são de verdade: a 2ª fica
    parada na trava do pedido até a 1ª terminar.

    O TransactionTestCase esvazia as tabelas no fim (inclusive as categorias
    criadas pela migration), por isso a categoria é recriada no setUp.
    """

    def setUp(self):
        Category.objects.get_or_create(slug='vestidos', defaults={'name': 'Vestidos'})
        self.order, self.variant = make_pending_order(make_customer())
        self.payment = make_pix_payment(self.order)

    def test_dois_avisos_simultaneos_confirmam_uma_vez(self):
        charge = gateway_order(self.payment)
        # A barreira segura as duas threads até AMBAS terem "consultado o
        # Mercado Pago". Assim elas entram na transação praticamente juntas.
        barrier = threading.Barrier(2, timeout=10)

        def fake_get_order(order_id):
            barrier.wait()
            return charge

        results = []
        errors = []

        def worker():
            try:
                results.append(webhook.process_order_notification(ORDER_ID))
            except Exception as error:  # noqa: BLE001 - o teste mostra qualquer erro
                errors.append(error)
            finally:
                connection.close()  # cada thread fecha a SUA conexão

        with mock.patch(GET_ORDER, side_effect=fake_get_order):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)

        self.assertEqual(errors, [])
        self.assertEqual(sorted(results), sorted([webhook.PAID, webhook.REPEATED]))
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(self.order.status, S.PAID)
        self.assertEqual(self.payment.status, P.APPROVED)
        self.assertEqual(self.variant.stock, 3)
