"""Painel da loja (Django Admin) para categorias e produtos."""

from django.contrib import admin

from .models import Category, Product, ProductImage, ProductVariant


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
        'name', 'category', 'price', 'total_stock', 'is_active', 'is_featured',
    )
    # Permite marcar ativo/destaque direto na listagem.
    list_editable = ('is_active', 'is_featured')
    list_filter = ('category', 'is_active', 'is_featured')
    search_fields = ('name', 'description')
    # O slug é preenchido sozinho a partir do nome.
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductVariantInline, ProductImageInline]

    def get_queryset(self, request):
        # prefetch_related busca todas as variações de uma vez só, em vez de
        # uma consulta por produto ao calcular total_stock (problema "N+1").
        return super().get_queryset(request).prefetch_related('variants')

    @admin.display(description='estoque total')
    def total_stock(self, obj):
        return obj.total_stock
