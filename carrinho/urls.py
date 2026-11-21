"""Rotas do carrinho. Ficam sob /carrinho/ (ver config/urls.py)."""

from django.urls import path

from . import views

urlpatterns = [
    path('', views.cart_detail, name='cart_detail'),
    # <int:...> só aceita números e já entrega o valor como int à view.
    path('adicionar/<int:product_id>/', views.cart_add, name='cart_add'),
    path('atualizar/<int:variant_id>/', views.cart_update, name='cart_update'),
    path('remover/<int:variant_id>/', views.cart_remove, name='cart_remove'),
]
