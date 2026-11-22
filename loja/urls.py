"""Rotas (URLs) das páginas públicas da loja.

O "name" de cada rota permite gerar o endereço nos templates com
{% url 'catalog' %}, sem escrever "/catalogo/" à mão. Se um dia o endereço
mudar, basta alterar aqui.
"""

from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('catalogo/', views.catalog, name='catalog'),
    # <slug:slug> captura o pedaço da URL e entrega à view como argumento.
    path('produto/<slug:slug>/', views.product_detail, name='product_detail'),
    path('sobre/', views.about, name='about'),
    path('contato/', views.contact, name='contact'),
    path('privacidade/', views.privacy, name='privacy'),
    path('termos/', views.terms, name='terms'),
]
