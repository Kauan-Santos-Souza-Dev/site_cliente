"""Context processors: dados disponíveis em TODOS os templates.

Um context processor é uma função que recebe o request e devolve um
dicionário. O Django junta esse dicionário ao contexto de cada template
renderizado. Assim o número do WhatsApp, por exemplo, fica em um só lugar
(settings/.env) e não precisa ser repetido em cada view.
"""

from django.conf import settings


def store_info(request):
    """Entrega aos templates os dados de contato e de identificação da loja."""
    return {
        'WHATSAPP_NUMBER': settings.WHATSAPP_NUMBER,
        'CONTACT_EMAIL': settings.CONTACT_EMAIL,
        'INSTAGRAM_HANDLE': settings.INSTAGRAM_HANDLE,
        'STORE_MOTTO': settings.STORE_MOTTO,
        # Identificação do fornecedor (Decreto 7.962/2013, art. 2º; decisão 85).
        # Vazios até a loja ter CNPJ; os templates mostram "[A DEFINIR PELA DONA]".
        'STORE_LEGAL_NAME': settings.STORE_LEGAL_NAME,
        'STORE_CNPJ': settings.STORE_CNPJ,
        'STORE_ADDRESS': settings.STORE_ADDRESS,
    }
