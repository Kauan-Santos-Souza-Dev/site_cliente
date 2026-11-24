"""Painel da loja (Django Admin): categorias, produtos e configuração da loja."""

from django.contrib import admin

from .models import Category, Product, ProductImage, ProductVariant, StoreSettings


class ProductVariantInline(admin.TabularInline):
    """Tamanhos e estoque editados dentro da página do produto."""

    model = ProductVariant
    extra = 1


class ProductImageInline(admin.TabularInline):
    """Fotos editadas dentro da página do produto."""

    model = ProductImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Categorias são fixas: podem ser editadas, mas não criadas nem apagadas."""

    list_display = ('name', 'slug')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Listagem útil de produtos, com busca, filtros e edição rápida."""

    list_display = (
        'name', 'category', 'price', 'max_installments', 'total_stock', 'is_active', 'is_featured',
    )
    # Permite marcar ativo/destaque e o limite de parcelas direto na listagem
    # (decisão 98): é assim que a dona muda vários produtos de uma vez. Os
    # validadores do model (1 a 12) valem também aqui.
    list_editable = ('is_active', 'is_featured', 'max_installments')
    actions = ['reset_installments']
    list_filter = ('category', 'is_active', 'is_featured')
    search_fields = ('name', 'description')
    # O slug é preenchido sozinho a partir do nome.
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductVariantInline, ProductImageInline]

    def get_queryset(self, request):
        # prefetch_related busca todas as variações de uma vez só, em vez de
        # uma consulta por produto ao calcular total_stock (problema "N+1").
        return super().get_queryset(request).prefetch_related('variants')

    @admin.action(description='Voltar à regra geral de parcelas da loja')
    def reset_installments(self, request, queryset):
        """Limpa o limite próprio dos produtos marcados (vazio = regra geral)."""
        updated = queryset.update(max_installments=None)
        self.message_user(request, f'{updated} produto(s) voltaram à regra geral de parcelas.')

    @admin.display(description='estoque total')
    def total_stock(self, obj):
        return obj.total_stock


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    """Configuração da loja: uma linha só, que se edita mas não se cria de novo nem se apaga."""

    list_display = (
        '__str__', 'reservation_minutes', 'free_shipping_threshold',
        'max_installments', 'min_installment_value', 'interest_policy',
    )
    fieldsets = (
        ('Reserva do estoque', {'fields': ('reservation_minutes',)}),
        ('Frete grátis', {'fields': ('free_shipping_threshold', 'free_shipping_is_provisional')}),
        ('Parcelamento no cartão', {'fields': ('max_installments', 'min_installment_value', 'interest_policy')}),
    )

    def has_add_permission(self, request):
        """Só permite "adicionar" se a linha ainda não existir."""
        return not StoreSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Sem a configuração, o checkout não saberia o prazo da reserva."""
        return False
