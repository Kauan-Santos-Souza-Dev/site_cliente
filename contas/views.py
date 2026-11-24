"""Views de conta: cadastro, verificação de e-mail e "Minha conta".

Login, logout, "esqueci a senha" e "trocar senha" usam as views prontas do
Django (ver contas/urls.py).

Segurança de "Minha conta" (contra IDOR):
nenhuma rota recebe o id de uma conta na URL. Toda view usa SEMPRE
`request.user`, a conta da sessão. Não existe endereço que mostre ou altere
os dados de outra pessoa.
"""

import json

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from pedidos.models import DELIVERED_ACTIVE_PERIOD, active_orders

from .emails import (
    send_account_exists_email,
    send_email_change_link,
    send_email_changed_notice,
    send_email_in_use_notice,
    send_verification_email,
)
from .forms import DeleteAccountForm, EmailChangeForm, ProfileForm, SignupForm
from .legal import PRIVACY_POLICY_VERSION, TERMS_VERSION
from .models import Consent
from .privacy import anonymize_user, export_user_data
from .tokens import get_user_from_verification_token, read_email_change_token

User = get_user_model()


def record_consent(user):
    """Grava o aceite das versões ATUAIS da Política e dos Termos (decisão 77)."""
    Consent.objects.create(
        user=user,
        privacy_policy_version=PRIVACY_POLICY_VERSION,
        terms_version=TERMS_VERSION,
    )


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
                # Dentro do mesmo atomic(): conta e aceite são gravados juntos.
                record_consent(user)
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
        # Quem refez o cadastro também marcou a caixa: registra o novo aceite.
        record_consent(existing)
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


# ---------------------------------------------------------------------------
# "Minha conta" (v2 Etapa 4, LGPD art. 18)
# ---------------------------------------------------------------------------

@login_required
def account(request):
    """Painel "Minha conta": mostra os dados guardados e leva às ações."""
    context = {'consents': request.user.consents.all()}
    return render(request, 'contas/account.html', context)


@login_required
def account_edit(request):
    """Corrigir nome e sobrenome (art. 18 III)."""
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Seus dados foram atualizados.')
            return redirect('account')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'contas/account_edit.html', {'form': form})


@login_required
def email_change(request):
    """Pede a troca de e-mail: envia um link ao NOVO endereço (decisão 81).

    A mensagem depois do envio é sempre a mesma, exista ou não outra conta
    com o novo e-mail (contra enumeração).
    """
    if request.method == 'POST':
        form = EmailChangeForm(request.user, request.POST)
        if form.is_valid():
            new_email = form.cleaned_data['new_email']
            existing = User.objects.filter(email=new_email).first()
            if existing is None:
                send_email_change_link(request, request.user, new_email)
            else:
                send_email_in_use_notice(request, request.user, existing)
            messages.info(
                request,
                'Se for possível usar este endereço, enviamos um link para ele. '
                'O e-mail da conta só muda depois que você abrir o link.',
            )
            return redirect('account')
    else:
        form = EmailChangeForm(request.user)
    return render(request, 'contas/email_change.html', {'form': form})


def email_change_confirm(request, token):
    """Abre o link do e-mail e troca o endereço da conta.

    Não exige login: o link pode ser aberto em outro aparelho. Quem prova a
    posse do novo e-mail é o próprio link, assinado e com validade.
    """
    user, new_email = read_email_change_token(token)
    if user is None:
        return render(request, 'contas/email_change_invalid.html', status=400)

    old_email = user.email
    user.email = new_email
    # Abrir o link prova que a cliente recebe e-mails no novo endereço.
    user.email_verified = True
    try:
        # atomic() isola a tentativa: se outra conta passou a usar este
        # e-mail depois que o link foi enviado, o banco recusa (unique).
        with transaction.atomic():
            user.save(update_fields=['email', 'email_verified'])
    except IntegrityError:
        return render(request, 'contas/email_change_invalid.html', status=400)

    send_email_changed_notice(old_email, user)
    return render(request, 'contas/email_change_done.html')


@login_required
@require_POST
def account_export(request):
    """Baixa um arquivo JSON com os dados da conta (art. 18 II e V).

    Só por POST (botão com CSRF): um link ou imagem em outro site não
    consegue disparar o download com a sessão da cliente.
    """
    data = export_user_data(request.user)
    # ensure_ascii=False mantém os acentos legíveis; indent deixa o arquivo
    # fácil de ler num editor de texto.
    content = json.dumps(data, ensure_ascii=False, indent=2)
    response = HttpResponse(content, content_type='application/json; charset=utf-8')
    # "attachment" faz o navegador baixar o arquivo em vez de abri-lo.
    response['Content-Disposition'] = 'attachment; filename="meus-dados-elegancia-crista.json"'
    return response


@login_required
def account_delete(request):
    """Exclui a conta: confirma com a senha e anonimiza (art. 18 VI, decisão 78).

    Contas do admin não se excluem por aqui: a dona trancaria o próprio
    painel. Isso é feito no servidor, por quem administra.
    Conta com pedido ativo também não (decisão 92).
    """
    if request.user.is_staff:
        messages.error(
            request,
            'Contas de administração não podem ser excluídas por esta página.',
        )
        return redirect('account')

    # Com pedido ativo (decisão 92), a exclusão fica bloqueada: a loja ainda
    # precisa entregar, receber ou devolver, e falar com a cliente. Vale para
    # GET (nem mostra o formulário) e POST (alguém enviando o form direto).
    blocking_orders = list(active_orders(request.user).values_list('pk', flat=True))
    if blocking_orders:
        context = {
            'blocking_orders': blocking_orders,
            'delivered_active_days': DELIVERED_ACTIVE_PERIOD.days,
        }
        return render(request, 'contas/account_delete.html', context)

    if request.method == 'POST':
        form = DeleteAccountForm(request.user, request.POST)
        if form.is_valid():
            anonymize_user(request.user)
            # logout() apaga a sessão atual (inclusive o carrinho).
            logout(request)
            return redirect('account_deleted')
    else:
        form = DeleteAccountForm(request.user)
    return render(request, 'contas/account_delete.html', {'form': form})


def account_deleted(request):
    """Página final: a conta foi excluída."""
    return render(request, 'contas/account_deleted.html')
