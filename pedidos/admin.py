"""Painel de pedidos e de frete para a dona da loja."""

from django.contrib import admin, messages

from .models import Order, OrderItem, ShippingRate
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
    """Lista de pedidos com busca, filtros e AÇÕES para mudar o status.

    O status é SÓ LEITURA (decisão 87). Ele muda por ações que respeitam a
    tabela de transições do model: "Marcar como enviado", "Marcar como
    entregue" e "Cancelar". A ação "Devolver peças ao estoque" (decisão 97)
    não muda o status: só devolve o estoque de um estorno de peça enviada.
    Não existe "marcar como pago": quem confirma pagamento é o gateway
    (Etapas 7 e 8). Assim nenhum clique por engano vira "pago".
    """

    list_display = ('id', 'customer_name', 'user', 'created_at', 'total_display', 'status', 'expires_at')
    list_display_links = ('id', 'customer_name')
    list_filter = ('status', 'created_at')
    # user__email: busca pelo e-mail da conta (o "__" atravessa a ligação).
    search_fields = ('id', 'customer_name', 'phone', 'user__email')
    # Sem date_hierarchy: ele usa CONVERT_TZ do MySQL, que exige as tabelas de
    # fuso horário instaladas no servidor (no Windows elas não vêm). O filtro
    # lateral por data acima funciona sem isso. Ver DECISIONS.md.
    readonly_fields = (
        'user', 'status', 'shipping_cost', 'total_display',
        'expires_at', 'shipped_at', 'delivered_at', 'stock_restored_at',
        'created_at', 'updated_at',
    )
    inlines = [OrderItemInline]
    actions = ['mark_shipped', 'mark_delivered', 'cancel_orders', 'restore_stock_action']
    fieldsets = (
        ('Pedido', {'fields': (
            'user', 'status', 'shipping_cost', 'total_display',
            'expires_at', 'shipped_at', 'delivered_at', 'stock_restored_at',
            'created_at', 'updated_at',
        )}),
        ('Entrega', {'fields': (
            'customer_name', 'phone', 'cep', 'street', 'number',
            'complement', 'neighborhood', 'city', 'state',
        )}),
    )

    def get_queryset(self, request):
        """Busca conta e itens de uma vez (evita "N+1": uma consulta por pedido)."""
        return super().get_queryset(request).select_related('user').prefetch_related('items')

    @admin.display(description='total')
    def total_display(self, order):
        return format_brl(order.total)

    # --- Permissões ----------------------------------------------------------

    def has_add_permission(self, request):
        """Pedidos nascem só pelo site: só o checkout reserva o estoque."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Só apaga pedido cancelado ou expirado.

        Esses nunca foram pagos e o estoque já voltou. Pedidos pagos,
        enviados ou estornados são registro de venda e seguem o prazo de
        guarda (decisão 79). Apagar um "aguardando pagamento" sumiria com as
        peças reservadas sem devolvê-las.
        """
        if obj is None:
            return super().has_delete_permission(request)
        return obj.status in (Order.Status.CANCELLED, Order.Status.EXPIRED)

    def get_actions(self, request):
        """Remove a exclusão em massa padrão, que ignoraria a regra acima."""
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    # --- Ações em massa ------------------------------------------------------

    def change_status(self, request, queryset, new_status):
        """Muda o status de cada pedido que PODE ir para new_status.

        Um por um, para cada save() aplicar a regra (trava, transição e
        estoque). Os que não podem (ex.: enviar um pedido não pago) são
        pulados e contados na mensagem.
        """
        changed = skipped = 0
        for order in queryset:
            if Order.can_change(order.status, new_status) and order.status != new_status:
                order.status = new_status
                order.save()
                changed += 1
            else:
                skipped += 1
        label = Order.Status(new_status).label.lower()
        self.message_user(request, f'{changed} pedido(s) marcado(s) como "{label}".', messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                f'{skipped} pedido(s) pulado(s): o status atual não permite essa mudança.',
                messages.WARNING,
            )

    @admin.action(description='Marcar como enviado (só pedidos pagos)')
    def mark_shipped(self, request, queryset):
        self.change_status(request, queryset, Order.Status.SHIPPED)

    @admin.action(description='Marcar como entregue (só pedidos enviados)')
    def mark_delivered(self, request, queryset):
        self.change_status(request, queryset, Order.Status.DELIVERED)

    @admin.action(description='Devolver peças ao estoque (só estorno de pedido enviado, com a peça já conferida)')
    def restore_stock_action(self, request, queryset):
        """Devolve o estoque de estornos de peças que já tinham sido enviadas.

        A dona só deve usar depois de RECEBER a peça de volta e conferir que
        está em bom estado. Cada devolução fica no histórico do pedido (quem e
        quando) e em stock_restored_at, e não se repete (decisão 97).
        """
        restored = skipped = 0
        for order in queryset:
            if order.restore_stock_manually():
                self.log_change(request, order, 'Estoque devolvido manualmente após conferir a peça.')
                restored += 1
            else:
                skipped += 1
        self.message_user(request, f'Estoque devolvido em {restored} pedido(s).', messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                f'{skipped} pedido(s) pulado(s): só vale para pedido estornado que tinha sido '
                'enviado e ainda não teve o estoque devolvido.',
                messages.WARNING,
            )

    @admin.action(description='Cancelar (só aguardando pagamento; devolve o estoque)')
    def cancel_orders(self, request, queryset):
        self.change_status(request, queryset, Order.Status.CANCELLED)


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    """Tabela de frete por UF (decisão 90). Preço editável direto na lista."""

    list_display = ('state', 'region', 'price', 'is_provisional')
    list_editable = ('price', 'is_provisional')
    list_filter = ('region', 'is_provisional')

    def changelist_view(self, request, extra_context=None):
        """Mostra um aviso no topo enquanto houver valor PROVISÓRIO."""
        provisional = ShippingRate.objects.filter(is_provisional=True).count()
        if provisional:
            self.message_user(
                request,
                f'{provisional} UF(s) com frete PROVISÓRIO (valor de exemplo). '
                'Confirme os valores reais com a dona e desmarque "PROVISÓRIO".',
                messages.WARNING,
            )
        return super().changelist_view(request, extra_context)
