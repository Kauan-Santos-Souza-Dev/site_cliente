"""Painel de pagamentos: só consulta (decisão 102).

Ninguém cria, edita ou apaga pagamento pelo admin: quem muda a situação de
uma cobrança é o próprio site, conversando com o Mercado Pago. Assim, um
clique por engano nunca vira "pago" nem some com um registro financeiro.
"""

from django.contrib import admin

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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
