"""Model de pagamentos: Payment, o "espelho" de uma cobrança no Mercado Pago (decisão 102)."""

import uuid

from django.db import models

from pedidos.models import Order


class Payment(models.Model):
    """Uma cobrança de um pedido no Mercado Pago (por enquanto, só Pix).

    O que fica aqui é só o necessário para ligar o pedido à cobrança e saber
    em que pé ela está: IDs do gateway, status, valor cobrado e prazos.
    NADA de CPF, dados de cartão ou dados do pagador (LGPD e regras do
    CLAUDE.md). O e-mail da cliente vai ao Mercado Pago, mas não é copiado
    para cá: ele já está na conta.
    """

    class Method(models.TextChoices):
        """Forma de pagamento. O cartão entra na v2 Etapa 8."""

        PIX = 'pix', 'Pix'

    class Status(models.TextChoices):
        """Situação da cobrança, do ponto de vista da loja.

        É diferente do status do PEDIDO: a cobrança pode estar "aprovada" e o
        pedido "expirado" (pagamento que chegou tarde, v2 Etapa 7b).
        """

        CREATING = 'criando', 'Criando no Mercado Pago'
        PENDING = 'pendente', 'Aguardando o pagamento'
        APPROVED = 'aprovado', 'Aprovado'
        CANCELLED = 'cancelado', 'Cancelado'
        EXPIRED = 'expirado', 'Expirado'
        # Os quatro abaixo são usados pelo webhook (v2 Etapa 7b).
        DIVERGENT = 'divergente', 'Valor divergente (conferir)'
        REFUND_PENDING = 'estorno_pendente', 'Estorno pendente'
        REFUNDED = 'estornado', 'Estornado'
        REFUND_FAILED = 'estorno_falhou', 'Estorno falhou (tentar de novo)'

    # PROTECT: um pedido com cobrança não pode ser apagado sem pensar
    # (a cobrança é registro financeiro).
    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, related_name='payments', verbose_name='pedido'
    )
    method = models.CharField('forma', max_length=10, choices=Method.choices)
    status = models.CharField(
        'situação', max_length=20, choices=Status.choices, default=Status.CREATING
    )
    # Valor cobrado, CONGELADO na criação (itens + frete). O webhook compara
    # o valor pago com este e com o total do pedido (v2 Etapa 7b).
    amount = models.DecimalField('valor (R$)', max_digits=10, decimal_places=2)

    # Chave de idempotência: vai no cabeçalho X-Idempotency-Key. Se a mesma
    # chave chegar duas vezes ao Mercado Pago (ex.: a 1ª tentativa caiu no
    # meio), ele devolve a MESMA cobrança em vez de criar outra. Por isso é
    # gravada ANTES da chamada e reaproveitada em toda nova tentativa.
    idempotency_key = models.UUIDField('chave de idempotência', default=uuid.uuid4, unique=True, editable=False)

    # IDs e status do lado do Mercado Pago (só texto de referência).
    gateway_order_id = models.CharField('ID da order no Mercado Pago', max_length=64, blank=True, db_index=True)
    gateway_payment_id = models.CharField('ID do pagamento no Mercado Pago', max_length=64, blank=True)
    gateway_status = models.CharField('status no Mercado Pago', max_length=40, blank=True)
    gateway_status_detail = models.CharField('detalhe do status no Mercado Pago', max_length=60, blank=True)

    # "Copia e cola" do Pix. Não é dado da cliente: é o código da cobrança da
    # loja, que morre quando o Pix expira. Guardado para redesenhar o QR Code
    # sem chamar o Mercado Pago a cada visita (decisão 102).
    pix_code = models.TextField('Pix copia e cola', blank=True)
    # Imagem do QR dinâmico retornada pela Orders API (Base64 PNG).
    qr_code_base64 = models.TextField('QR Code (Base64)', blank=True)

    expires_at = models.DateTimeField('Pix expira em', null=True, blank=True)
    approved_at = models.DateTimeField('aprovado em', null=True, blank=True)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'pagamento'
        verbose_name_plural = 'pagamentos'
        ordering = ['-created_at']
        constraints = [
            # Uma cobrança de cada forma por pedido. Um Pix expirado leva o
            # pedido junto (decisão 103), então nunca é preciso um 2º Pix.
            # É uma constraint SEM condição: o MySQL não aceita as condicionais.
            models.UniqueConstraint(fields=['order', 'method'], name='one_payment_per_method'),
        ]

    def __str__(self):
        return f'Pagamento nº {self.pk} ({self.get_method_display()}) do pedido nº {self.order_id}'

    @property
    def external_reference(self):
        """Referência que mandamos ao Mercado Pago e que volta nas consultas.

        Leva o número do PAGAMENTO (não dados da cliente). O webhook usa esta
        referência para achar a cobrança (v2 Etapa 7b).
        """
        return f'pagamento-{self.pk}'
