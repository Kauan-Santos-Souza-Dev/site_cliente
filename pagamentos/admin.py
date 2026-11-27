"""Painel de pagamentos: só consulta (decisão 102).

Ninguém cria, edita ou apaga pagamento pelo admin: quem muda a situação de
uma cobrança é o próprio site, conversando com o Mercado Pago. Assim, um
clique por engano nunca vira "pago" nem some com um registro financeiro.
"""

from django.contrib import admin, messages

from pedidos.whatsapp import format_brl

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Lista de cobranças com filtros, só leitura."""

    list_display = ('id', 'order', 'method', 'status', 'amount_display', 'gateway_status', 'expires_at', 'created_at')
    list_filter = ('status', 'method', 'created_at')
    # Busca pelo número do pedido ou pelo ID do Mercado Pago (para conferir no painel dele).
    search_fields = ('order__id', 'gateway_order_id', 'gateway_payment_id')
    list_select_related = ('order',)
    # O "copia e cola" e a chave de idempotência não aparecem: não ajudam a
    # dona e só poluiriam a tela.
    fields = (
        'order', 'method', 'status', 'amount',
        'gateway_order_id', 'gateway_payment_id', 'gateway_status', 'gateway_status_detail',
        'expires_at', 'approved_at', 'created_at', 'updated_at',
    )
    readonly_fields = fields

    @admin.display(description='valor')
    def amount_display(self, payment):
        return format_brl(payment.amount)

    def changelist_view(self, request, extra_context=None):
        """Mostra um aviso no topo enquanto houver cobrança que pede decisão da dona.

        Mesmo padrão do aviso de frete provisório (pedidos/admin.py,
        ShippingRateAdmin). Os dois casos vêm do webhook (decisões 107 e 108):
        - "Pago após expirar": dinheiro recebido para um pedido que já tinha
          expirado ou sido cancelado. A dona decide se entrega ou estorna.
        - "Valor divergente": o Mercado Pago diz que foi pago, mas o valor ou
          a referência não batem com o pedido. O pedido NÃO virou "pago".
        O aviso some sozinho quando não houver mais nenhum desses casos.
        """
        late = Payment.objects.filter(status=Payment.Status.LATE_PAID).count()
        divergent = Payment.objects.filter(status=Payment.Status.DIVERGENT).count()
        if late:
            self.message_user(
                request,
                f'{late} pagamento(s) "Pago após expirar": o dinheiro chegou depois que o pedido '
                'expirou ou foi cancelado. Decida com a cliente se entrega (se ainda houver a peça) '
                'ou estorna. Use o filtro "situação" para encontrá-los.',
                messages.WARNING,
            )
        if divergent:
            self.message_user(
                request,
                f'{divergent} pagamento(s) com "Valor divergente": o valor pago não bate com o pedido. '
                'Confira no painel do Mercado Pago antes de qualquer envio. Use o filtro "situação".',
                messages.WARNING,
            )
        return super().changelist_view(request, extra_context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
