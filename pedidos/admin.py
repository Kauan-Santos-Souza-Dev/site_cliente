"""Painel de pedidos para a dona da loja."""

from django.contrib import admin, messages

from .models import Order, OrderItem
from .whatsapp import format_brl


class OrderItemInline(admin.TabularInline):
    """Itens do pedido, só para leitura: o pedido já foi fechado pela cliente."""

    model = OrderItem
    extra = 0
    can_delete = False
    fields = ('product_name', 'size', 'quantity', 'unit_price', 'subtotal_display')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='subtotal')
    def subtotal_display(self, item):
        return format_brl(item.subtotal)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Lista de pedidos com busca, filtros e troca rápida de status."""

    list_display = ('id', 'customer_name', 'phone', 'created_at', 'total_display', 'status')
    list_display_links = ('id', 'customer_name')
    # Muda o status direto na lista. O Order.save() devolve o estoque ao cancelar,
    # e o Order.clean() impede reabrir um pedido cancelado.
    list_editable = ('status',)
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'customer_name', 'phone')
    # Sem date_hierarchy: ele usa CONVERT_TZ do MySQL, que exige as tabelas de
    # fuso horário instaladas no servidor (no Windows elas não vêm). O filtro
    # lateral por data acima funciona sem isso. Ver DECISIONS.md.
    readonly_fields = ('created_at', 'updated_at', 'total_display')
    inlines = [OrderItemInline]
    actions = ['cancel_orders']
    fieldsets = (
        ('Pedido', {'fields': ('status', 'shipping_cost', 'total_display', 'created_at', 'updated_at')}),
        ('Cliente', {'fields': ('customer_name', 'phone')}),
        ('Entrega', {'fields': ('cep', 'street', 'number', 'complement', 'neighborhood', 'city', 'state')}),
    )

    def get_queryset(self, request):
        # Busca os itens de todos os pedidos da página de uma vez (evita "N+1").
        return super().get_queryset(request).prefetch_related('items')

    @admin.display(description='total')
    def total_display(self, order):
        return format_brl(order.total)

    # --- Permissões ----------------------------------------------------------

    def has_add_permission(self, request):
        """Pedidos nascem só pelo site: só o checkout desconta o estoque."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Só apaga pedido cancelado ou enviado.

        Apagar um pedido "novo" ou "confirmado" sumiria com as peças
        reservadas sem devolvê-las ao estoque. Cancele primeiro.
        """
        if obj is None:
            return super().has_delete_permission(request)
        return obj.status in (Order.Status.CANCELLED, Order.Status.SHIPPED)

    def get_actions(self, request):
        """Remove a exclusão em massa padrão, que ignoraria a regra acima."""
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    # --- Ações em massa ------------------------------------------------------

    @admin.action(description='Cancelar pedidos selecionados (devolve o estoque)')
    def cancel_orders(self, request, queryset):
        """Cancela um por um, para cada save() devolver o estoque do pedido."""
        cancelled = 0
        for order in queryset.exclude(status=Order.Status.CANCELLED):
            order.status = Order.Status.CANCELLED
            order.save()
            cancelled += 1
        self.message_user(request, f'{cancelled} pedido(s) cancelado(s).', messages.SUCCESS)
