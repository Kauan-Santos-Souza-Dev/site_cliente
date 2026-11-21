"""Context processors: dados disponíveis em TODOS os templates.

Um context processor é uma função que recebe o request e devolve um
dicionário. O Django junta esse dicionário ao contexto de cada template
renderizado. Assim o número do WhatsApp, por exemplo, fica em um só lugar
(settings/.env) e não precisa ser repetido em cada view.
"""

from django.conf import settings


def store_info(request):
    """Entrega aos templates os dados de contato da loja."""
    return {
        'WHATSAPP_NUMBER': settings.WHATSAPP_NUMBER,
        'CONTACT_EMAIL': settings.CONTACT_EMAIL,
        'INSTAGRAM_HANDLE': settings.INSTAGRAM_HANDLE,
        'STORE_MOTTO': settings.STORE_MOTTO,
    }
