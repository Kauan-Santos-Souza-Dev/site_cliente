"""Rotas de pedido. Ficam sob /pedido/ (ver config/urls.py)."""

from django.urls import path

from . import views

urlpatterns = [
    path('finalizar/', views.checkout, name='checkout'),
    path('confirmado/', views.order_confirmation, name='order_confirmation'),
]
