"""Validações de upload de imagens enviadas pelo admin."""

from pathlib import Path

from django.core.exceptions import ValidationError

# Formatos aceitos e tamanho máximo (2 MB).
ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')
MAX_IMAGE_SIZE = 2 * 1024 * 1024


def validate_image_file(image):
    """Rejeita imagens com formato não permitido ou maior que 2 MB.

    Observação: o ImageField já confere (via Pillow) se o arquivo é mesmo uma
    imagem; aqui só limitamos o formato e o tamanho.
    """
    extension = Path(image.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError('Formato não permitido. Use JPG, PNG ou WebP.')
    if image.size > MAX_IMAGE_SIZE:
        raise ValidationError('A imagem é grande demais. O limite é de 2 MB.')
