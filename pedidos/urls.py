"""Rotas de pedido. Ficam sob /pedido/ (ver config/urls.py)."""

from django.urls import path

from . import views

urlpatterns = [
    path('finalizar/', views.checkout, name='checkout'),
    # "Meus pedidos" (v2 Etapa 5). O <int:pk> aceita só números; a view
    # confere se o pedido é da conta logada (contra IDOR).
    path('meus-pedidos/', views.my_orders, name='my_orders'),
    path('meus-pedidos/<int:pk>/', views.order_detail, name='order_detail'),
]
