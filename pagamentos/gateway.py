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
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.conf import settings

logger = logging.getLogger('pagamentos')

# Tempo máximo (segundos) esperando o Mercado Pago responder. Sem isso, uma
# lentidão do gateway prenderia a página da cliente por muito tempo.
REQUEST_TIMEOUT = 20


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
    payment_id: str
    pix_code: str


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


def _request_options(idempotency_key):
    """Opções da requisição: cabeçalho X-Idempotency-Key e tempo máximo de espera.

    Idempotência: mandar a mesma chave de novo NÃO cria uma segunda cobrança;
    o Mercado Pago devolve a primeira. Isso protege contra clique duplo e
    contra a tentativa repetida depois de uma queda de rede.
    """
    from mercadopago.config import RequestOptions

    options = RequestOptions(connection_timeout=REQUEST_TIMEOUT)
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
    Não usamos o qr_code_base64 (imagem pronta): desenhamos o QR nós mesmos.
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
        payment_id=str(first_payment.get('id') or ''),
        pix_code=str(payment_method.get('qr_code') or ''),
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
