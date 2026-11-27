"""Rotas de pagamento. Ficam sob /pagamentos/ (ver config/urls.py)."""

from django.urls import path

from . import views

urlpatterns = [
    # Só POST: gera (ou reaproveita) o Pix do pedido e redireciona para o QR.
    path('pedido/<int:pk>/pix/gerar/', views.start_pix, name='start_pix'),
    # Página com o QR Code e o "copia e cola".
    path('pedido/<int:pk>/pix/', views.pix_page, name='pix_page'),
    # JSON com a situação do pedido, consultado pelo JavaScript da página do Pix.
    path('pedido/<int:pk>/pix/situacao/', views.pix_status, name='pix_status'),
    # Webhook do Mercado Pago (POST público, sem CSRF, protegido pela
    # assinatura). É ESTA a URL que vai no painel do Mercado Pago.
    path('webhook/mercadopago/', views.mercadopago_webhook, name='mercadopago_webhook'),
]
