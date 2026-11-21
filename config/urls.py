"""Rotas (URLs) principais do projeto."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    # API pública somente leitura (etapa 5).
    path('api/', include('loja.api_urls')),
    # Carrinho na sessão (etapa 6).
    path('carrinho/', include('carrinho.urls')),
    # Checkout e confirmação do pedido (etapa 7).
    path('pedido/', include('pedidos.urls')),
    # include() "pendura" as rotas do app loja na raiz do site.
    path('', include('loja.urls')),
]

# Em desenvolvimento (DEBUG=True), o próprio Django serve as fotos enviadas
# pelo admin (pasta media/). Em produção, quem faz isso é o servidor web.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
