"""Views de conta. Login e logout usam as views prontas do Django (ver contas/urls.py).

Só o cadastro é uma view nossa, porque o Django não traz uma.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import SignupForm


def get_safe_next_url(request, url):
    """Devolve `url` se ela for deste site; senão, a página inicial.

    Contra "open redirect": um link malicioso como
    /conta/cadastro/?next=https://site-falso.com faria a cliente, logo depois
    de se cadastrar, cair numa cópia falsa da loja pedindo dados. A função do
    Django abaixo só aceita endereços do nosso próprio domínio. É a mesma
    proteção que o LoginView do Django aplica no login.
    """
    is_safe = url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )
    if url and is_safe:
        return url
    return resolve_url(settings.LOGIN_REDIRECT_URL)


def signup(request):
    """GET: mostra o cadastro. POST: cria a conta, já entra e volta para onde estava."""
    if request.user.is_authenticated:
        return redirect('home')

    # "next" é a página para onde voltar depois (ex.: o checkout, na Etapa 5).
    next_url = request.POST.get('next') or request.GET.get('next', '')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # login() grava a conta na sessão. Ele troca o código da sessão
            # (proteção contra "session fixation"), mas MANTÉM os dados dela:
            # o carrinho montado antes do cadastro continua lá (decisão 67).
            login(request, user)
            messages.success(request, f'Boas-vindas, {user.first_name}! Sua conta foi criada.')
            return redirect(get_safe_next_url(request, next_url))
    else:
        form = SignupForm()

    return render(request, 'contas/signup.html', {'form': form, 'next': next_url})
