"""Views de conta: cadastro, verificação de e-mail e reenvio do link.

Login, logout e "esqueci a senha" usam as views prontas do Django
(ver contas/urls.py).
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .emails import send_account_exists_email, send_verification_email
from .forms import SignupForm
from .tokens import get_user_from_verification_token

User = get_user_model()


def signup(request):
    """GET: mostra o cadastro. POST válido: trata o cadastro e SEMPRE mostra a mesma página.

    Não há login automático (decisão 73): a conta só é usada depois que a
    dona do e-mail confirma pelo link. A resposta é idêntica para e-mail
    novo e e-mail já cadastrado, então ninguém descobre quem é cliente
    da loja tentando se cadastrar (enumeração).
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            register_signup(request, form)
            # Post/Redirect/Get: recarregar a página não reenvia o cadastro.
            return redirect('signup_done')
    else:
        form = SignupForm()

    return render(request, 'contas/signup.html', {'form': form})


def register_signup(request, form):
    """Decide o que fazer com um cadastro válido. Nada daqui aparece na tela.

    - E-mail novo: cria a conta e envia o link de verificação.
    - E-mail de conta VERIFICADA: não muda nada; envia um aviso à dona.
    - E-mail de conta NÃO verificada: o cadastro novo substitui nome e senha
      e um link novo é enviado. Protege contra o "pré-sequestro": alguém que
      cadastrou o e-mail da vítima com uma senha que ele conhece perde essa
      senha (e as sessões abertas dele, pois o Django invalida as sessões
      quando a senha muda) antes de a vítima verificar a conta.
    """
    email = form.cleaned_data['email']
    existing = User.objects.filter(email=email).first()

    if existing is None:
        try:
            # atomic() cria um "ponto de volta": se outra requisição cadastrou
            # o mesmo e-mail no mesmo instante, o banco recusa (unique) e só
            # este trecho é desfeito.
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            existing = User.objects.get(email=email)
        else:
            send_verification_email(request, user)
            return

    password = form.cleaned_data['password1']
    if existing.email_verified:
        # Calcula um hash à toa para que este caminho demore parecido com o
        # de uma conta nova (o Argon2 leva um tempinho). Reduz a chance de
        # alguém descobrir que o e-mail existe medindo o tempo de resposta.
        make_password(password)
        send_account_exists_email(request, existing)
    else:
        existing.first_name = form.cleaned_data['first_name']
        existing.last_name = form.cleaned_data['last_name']
        existing.set_password(password)  # guarda o hash, nunca a senha
        existing.save()
        send_verification_email(request, existing)


def signup_done(request):
    """Página "confira seu e-mail", igual para qualquer cadastro."""
    return render(request, 'contas/signup_done.html')


def verify_email(request, token):
    """Abre o link do e-mail: confere o token e marca o e-mail como verificado.

    O link chega por GET (é um link clicado no e-mail). Abrir o mesmo link
    duas vezes não faz mal: a conta só continua verificada.
    """
    user = get_user_from_verification_token(token)
    if user is None:
        # Token adulterado, vencido (mais de 24 h) ou de um e-mail que mudou.
        return render(request, 'contas/verify_invalid.html', status=400)

    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=['email_verified'])
    return render(request, 'contas/verify_done.html')


@login_required
def verification_pending(request):
    """Para quem está logada sem ter verificado o e-mail: explica e reenvia o link.

    GET mostra a página; POST pede um link novo. A mensagem depois do POST é
    sempre a mesma, tenha o e-mail saído agora ou não (limite de frequência).
    """
    if request.user.email_verified:
        return redirect('cart_detail')
    return render(request, 'contas/verification_pending.html')


@login_required
@require_POST
def resend_verification(request):
    """Envia um novo link de verificação (respeitando o intervalo mínimo)."""
    if not request.user.email_verified:
        send_verification_email(request, request.user)
    messages.info(
        request,
        'Se for possível, enviamos um novo link para o seu e-mail. '
        'Pedidos seguidos precisam de alguns minutos de intervalo.',
    )
    return redirect('verification_pending')
