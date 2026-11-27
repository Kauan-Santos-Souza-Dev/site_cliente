"""Conversa com o Mercado Pago. É o ÚNICO arquivo do projeto que usa o SDK (decisão 101).

Por que isolar aqui?
- O resto do site chama funções simples (create_pix_order...) e recebe
  objetos simples (GatewayOrder). Se um dia o SDK mudar, ou trocarmos de
  gateway, só este arquivo muda.
- Nos testes, simulamos ESTE arquivo (unittest.mock.patch): nenhum teste
  faz chamada de rede de verdade (regra do CLAUDE.md).

API usada: "Orders API" (POST /v1/orders), a recomendada hoje pela
documentação do Pix do Mercado Pago (decisão 100).

Segurança:
- O Access Token vem do .env (settings.MERCADOPAGO_ACCESS_TOKEN) e NUNCA vai
  para log nem para mensagem de erro.
- Os logs levam só o tipo de operação e o código HTTP: nada do corpo da
  resposta (que traz e-mail da pagadora e o "copia e cola").
"""

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.conf import settings

logger = logging.getLogger('pagamentos')

# Tempo máximo (segundos) esperando o Mercado Pago responder. Sem isso, uma
# lentidão do gateway prenderia a página da cliente por muito tempo.
REQUEST_TIMEOUT = 20.0

# Tempo máximo das chamadas feitas DENTRO do webhook (consultar a order) e do
# cancelamento. O Mercado Pago espera a resposta do webhook por até 22 s; com
# 10 s de consulta, sobra folga para o resto (banco, resposta).
WEBHOOK_REQUEST_TIMEOUT = 10.0

# Status da order que significam "Pix pago" (documentação "Status da order").
# Os dois precisam bater: "processed" sozinho também aparece em reembolso
# parcial (status_detail "partially_refunded").
PAID_STATUS = 'processed'
PAID_STATUS_DETAIL = 'accredited'


class GatewayError(Exception):
    """O Mercado Pago não respondeu ou recusou o pedido.

    A mensagem é genérica DE PROPÓSITO: o detalhe técnico não vai para a
    tela da cliente nem para o log.
    """


@dataclass
class GatewayOrder:
    """Resumo de uma "order" do Mercado Pago, só com o que o site usa."""

    id: str
    status: str
    status_detail: str
    external_reference: str
    total_amount: Decimal | None
    # Quanto o Mercado Pago diz que FOI PAGO (o webhook confere com o pedido).
    total_paid_amount: Decimal | None
    payment_id: str
    pix_code: str
    qr_code_base64: str


def is_configured():
    """True se há Access Token no .env (sem ele, o pagamento online fica desligado)."""
    return bool(settings.MERCADOPAGO_ACCESS_TOKEN)


def format_amount(amount):
    """Decimal -> texto com 2 casas ("150.00"), como a Orders API pede.

    Recusa float: dinheiro é sempre Decimal no projeto (CLAUDE.md).
    """
    if not isinstance(amount, Decimal):
        raise TypeError('O valor precisa ser Decimal, nunca float.')
    return str(amount.quantize(Decimal('0.01')))


def parse_amount(text):
    """Texto do Mercado Pago ("150.00") -> Decimal. None se vier vazio ou inválido.

    Decimal(str(...)) e nunca float: 0.1 + 0.2 em float dá 0.30000000000000004.
    """
    if text in (None, ''):
        return None
    try:
        return Decimal(str(text))
    except InvalidOperation:
        return None


def _sdk():
    """Cria o cliente do SDK com o Access Token do .env.

    O import fica AQUI DENTRO (e não no topo do arquivo): o resto do site e os
    testes funcionam mesmo antes de o SDK ser instalado, e só quem realmente
    fala com o Mercado Pago precisa dele.
    """
    if not is_configured():
        raise GatewayError('Pagamento online não configurado.')
    import mercadopago

    return mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)


def _request_options(idempotency_key=None, timeout=REQUEST_TIMEOUT):
    """Opções da requisição: cabeçalho X-Idempotency-Key e tempo máximo de espera.

    Idempotência: mandar a mesma chave de novo NÃO cria uma segunda cobrança;
    o Mercado Pago devolve a primeira. Isso protege contra clique duplo e
    contra a tentativa repetida depois de uma queda de rede.

    Sem idempotency_key, o próprio SDK põe uma chave ALEATÓRIA em cada
    chamada. Numa consulta (GET) isso não importa: consultar não muda nada.
    O SDK exige o tempo como float (RequestOptions recusa int).
    """
    from mercadopago.config import RequestOptions

    options = RequestOptions(connection_timeout=float(timeout))
    if idempotency_key is not None:
        options.custom_headers = {'x-idempotency-key': str(idempotency_key)}
    return options


def _call(operation, function, *args):
    """Executa uma chamada do SDK e devolve o corpo da resposta (dicionário).

    O SDK devolve {"status": <código HTTP>, "response": <corpo>}. Qualquer
    código fora de 200/201, ou erro de rede, vira GatewayError. O log diz só
    a operação e o código HTTP.
    """
    try:
        result = function(*args)
    except Exception:  # erro de rede, tempo esgotado etc. (vindo do requests)
        logger.warning('Mercado Pago: falha de comunicação em "%s".', operation)
        raise GatewayError('Falha de comunicação com o Mercado Pago.') from None
    http_status = result.get('status')
    if http_status not in (200, 201):
        logger.warning('Mercado Pago: "%s" recusado (HTTP %s).', operation, http_status)
        raise GatewayError('O Mercado Pago recusou a operação.')
    return result.get('response') or {}


def _to_gateway_order(body):
    """Transforma o JSON da order do Mercado Pago num GatewayOrder.

    Onde ficam os dados do Pix (documentação da Orders API):
    transactions.payments[0].payment_method.qr_code = "copia e cola".
    O Mercado Pago retorna o copia e cola e a imagem QR em Base64.
    """
    payments = (body.get('transactions') or {}).get('payments') or [{}]
    first_payment = payments[0] or {}
    payment_method = first_payment.get('payment_method') or {}
    return GatewayOrder(
        id=str(body.get('id') or ''),
        status=str(body.get('status') or ''),
        status_detail=str(body.get('status_detail') or ''),
        external_reference=str(body.get('external_reference') or ''),
        total_amount=parse_amount(body.get('total_amount')),
        total_paid_amount=parse_amount(body.get('total_paid_amount')),
        payment_id=str(first_payment.get('id') or ''),
        pix_code=str(payment_method.get('qr_code') or ''),
        qr_code_base64=str(payment_method.get('qr_code_base64') or ''),
    )


def build_pix_order_body(*, reference, amount, payer_email, expiration_minutes):
    """Monta o corpo do POST /v1/orders para um Pix (separado para ser testado).

    - total_amount e amount vão como TEXTO com 2 casas (format_amount).
    - expiration_time: duração no formato ISO 8601 ("PT30M" = 30 minutos).
      O Mercado Pago aceita de 30 minutos a 30 dias.
    - payer: só o e-mail (obrigatório). SEM CPF (decisão 59) e sem nome.
      Exceção: no sandbox, MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME=APRO faz o
      Mercado Pago aprovar o Pix de teste sozinho. Em produção, fica vazio.
    """
    payer = {'email': payer_email}
    if settings.MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME:
        payer['first_name'] = settings.MERCADOPAGO_SANDBOX_PAYER_FIRST_NAME
    total = format_amount(amount)
    return {
        'type': 'online',
        'processing_mode': 'automatic',
        'external_reference': reference,
        'total_amount': total,
        'payer': payer,
        'transactions': {
            'payments': [{
                'amount': total,
                'payment_method': {'id': 'pix', 'type': 'bank_transfer'},
                'expiration_time': f'PT{int(expiration_minutes)}M',
            }],
        },
    }


def create_pix_order(*, reference, amount, payer_email, expiration_minutes, idempotency_key):
    """Cria a cobrança Pix no Mercado Pago e devolve um GatewayOrder (com o "copia e cola").

    Lança GatewayError se o Mercado Pago recusar ou não responder.
    """
    sdk = _sdk()
    body = build_pix_order_body(
        reference=reference, amount=amount,
        payer_email=payer_email, expiration_minutes=expiration_minutes,
    )
    response = _call('criar Pix', sdk.order().create, body, _request_options(idempotency_key))
    return _to_gateway_order(response)


def get_order(order_id):
    """Consulta a order no Mercado Pago (GET /v1/orders/{id}) e devolve um GatewayOrder.

    É a "reconsulta" do webhook: o aviso só diz "algo mudou na order X";
    O QUE mudou a gente pergunta direto ao Mercado Pago, com o nosso Access
    Token. Assim, um aviso forjado nunca consegue marcar um pedido como pago.

    Lança GatewayError se o Mercado Pago recusar ou não responder.
    """
    sdk = _sdk()
    options = _request_options(timeout=WEBHOOK_REQUEST_TIMEOUT)
    response = _call('consultar order', sdk.order().get, str(order_id), options)
    return _to_gateway_order(response)


def cancel_order(order_id):
    """Cancela a order (o Pix) no Mercado Pago: POST /v1/orders/{id}/cancel.

    Só funciona com a order ainda pendente ("action_required" ou "created",
    segundo a documentação). Sem corpo; o X-Idempotency-Key é obrigatório.

    Por que uma chave NOVA (uuid4) e não a do Payment? A do Payment já foi
    usada para CRIAR a order; reusá-la aqui daria erro 409
    ("idempotency_key_already_used"). Cancelar duas vezes não faz mal: a 2ª
    só recebe "já cancelada".

    Lança GatewayError se o Mercado Pago recusar ou não responder.
    """
    sdk = _sdk()
    options = _request_options(uuid.uuid4(), timeout=WEBHOOK_REQUEST_TIMEOUT)
    response = _call('cancelar order', sdk.order().cancel, str(order_id), options)
    return _to_gateway_order(response)


def is_paid(charge):
    """True se a order do Mercado Pago está paga ("processed" + "accredited")."""
    return charge.status == PAID_STATUS and charge.status_detail == PAID_STATUS_DETAIL


def _signature_matches(x_signature, x_request_id, data_id, secret):
    """Usa o validador OFICIAL do SDK. Devolve None se confere, ou o motivo da recusa.

    Como funciona a assinatura (HMAC)?
    O Mercado Pago junta "id:<data.id>;request-id:<x-request-id>;ts:<ts>;"
    e calcula um HMAC-SHA256 desse texto com a CHAVE SECRETA que só ele e a
    loja conhecem. O resultado vai no cabeçalho x-signature ("ts=...,v1=...").
    A loja refaz a conta com a mesma chave: se o resultado bate, o aviso veio
    de quem conhece a chave. Quem não tem a chave não consegue forjar o v1.
    O SDK compara em "tempo constante" (hmac.compare_digest), o que impede
    descobrir a assinatura medindo quanto tempo a comparação demora.
    """
    from mercadopago.webhook import InvalidWebhookSignatureError, WebhookSignatureValidator

    try:
        WebhookSignatureValidator.validate(x_signature, x_request_id, data_id, secret)
    except InvalidWebhookSignatureError as error:
        return error.reason.value
    return None


def is_webhook_signature_valid(x_signature, x_request_id, data_id):
    """Confere se o aviso do webhook foi assinado com a nossa chave secreta.

    Tenta com o data.id exatamente como chegou (é o que o SDK faz). Se falhar
    e o ID tiver letras maiúsculas, tenta de novo em minúsculas: uma versão
    da documentação do Mercado Pago manda usar o ID alfanumérico em
    minúsculas, e os IDs da Orders API são maiúsculos ("ORD01..."). As duas
    tentativas exigem a chave secreta, então a segurança é a mesma
    (decisão 106; confirmar no sandbox qual das duas é a usada).

    Log: só o MOTIVO da recusa (ex.: "SignatureMismatch") e, no acerto,
    QUAL tentativa bateu ("original" ou "minúscula"). Nunca a chave, os
    cabeçalhos, a assinatura ou o próprio ID.
    """
    secret = settings.MERCADOPAGO_WEBHOOK_SECRET
    if not secret:
        return False
    attempt = 'original'
    reason = _signature_matches(x_signature, x_request_id, data_id, secret)
    if reason is not None and data_id and data_id != data_id.lower():
        attempt = 'minúscula'
        reason = _signature_matches(x_signature, x_request_id, data_id.lower(), secret)
    if reason is not None:
        logger.warning('Webhook recusado: assinatura inválida (%s).', reason)
        return False
    # LOG TEMPORÁRIO (decisão 106): serve só para descobrir, no teste do
    # sandbox, qual das duas tentativas o Mercado Pago usa. Depois do teste,
    # remova a tentativa que não bateu E esta linha.
    logger.info('Webhook: assinatura conferida com o ID %s (log temporário, decisão 106).', attempt)
    return True
