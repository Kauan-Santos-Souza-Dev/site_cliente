"""Decorator que exige conta com e-mail verificado (decisão 72)."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect


def verified_email_required(view):
    """Só deixa passar quem está logada E já verificou o e-mail.

    Um "decorator" envolve uma view com uma checagem antes dela. Uso:

        @verified_email_required
        def checkout(request): ...

    - Sem login: vai para a página de login, com ?next= para voltar depois.
    - Logada, mas sem verificar: vai para a página que explica e reenvia o link.
    """

    @wraps(view)  # mantém o nome e a docstring da view original
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.email_verified:
            return redirect('verification_pending')
        return view(request, *args, **kwargs)

    return wrapper
