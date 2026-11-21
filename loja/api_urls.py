"""Rotas da API. Ficam todas sob /api/ (ver config/urls.py)."""

from django.urls import path

from . import api_views

urlpatterns = [
    path('categorias/', api_views.CategoryListAPIView.as_view(), name='api_categories'),
    path('produtos/', api_views.ProductListAPIView.as_view(), name='api_products'),
    # as_view() transforma a classe em uma função que o Django sabe chamar.
    path('produtos/<slug:slug>/', api_views.ProductDetailAPIView.as_view(), name='api_product_detail'),
]
