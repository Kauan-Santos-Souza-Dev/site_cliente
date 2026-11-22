"""Rotas de conta. Ficam sob /conta/ (ver config/urls.py).

Login, logout e redefinição de senha usam as views PRONTAS do Django,
apenas configuradas aqui. É uma exceção consciente à decisão 20 (views em
função): em autenticação, código revisado por muita gente é mais seguro
(decisão 65). Elas validam o "next" contra open redirect, trocam o código
da sessão no login, só aceitam logout por POST e, no "esqueci a senha",
respondem igual exista o e-mail ou não.
"""

from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm, ResetForm

urlpatterns = [
    # --- Entrar e sair ------------------------------------------------------
    path(
        'entrar/',
        auth_views.LoginView.as_view(
            template_name='contas/login.html',
            authentication_form=LoginForm,
            # Quem já está logado e abre /conta/entrar/ vai direto para o início.
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    # Só aceita POST: um link ou imagem em outro site não consegue deslogar a
    # cliente sem ela querer. O botão "Sair" do menu é um formulário com CSRF.
    path('sair/', auth_views.LogoutView.as_view(), name='logout'),

    # --- Cadastro e verificação de e-mail (decisões 72 e 73) ---------------
    path('cadastro/', views.signup, name='signup'),
    path('cadastro/enviado/', views.signup_done, name='signup_done'),
    # <str:token> aceita qualquer texto sem "/" (o token assinado não tem barras).
    path('verificar/<str:token>/', views.verify_email, name='verify_email'),
    path('verificacao-pendente/', views.verification_pending, name='verification_pending'),
    path('verificacao-pendente/reenviar/', views.resend_verification, name='resend_verification'),

    # --- Minha conta (v2 Etapa 4, LGPD) --------------------------------------
    # Nenhuma rota tem id de conta: todas agem sobre a conta logada (contra IDOR).
    path('minha-conta/', views.account, name='account'),
    path('minha-conta/dados/', views.account_edit, name='account_edit'),
    path('minha-conta/email/', views.email_change, name='email_change'),
    path('minha-conta/email/confirmar/<str:token>/', views.email_change_confirm, name='email_change_confirm'),
    # Trocar a senha: view pronta do Django (mesmo motivo da decisão 65). Ela
    # pede a senha atual e mantém a cliente logada NESTE aparelho, derrubando
    # as sessões abertas em outros.
    path(
        'minha-conta/senha/',
        auth_views.PasswordChangeView.as_view(template_name='contas/password_change.html'),
        name='password_change',
    ),
    path(
        'minha-conta/senha/alterada/',
        auth_views.PasswordChangeDoneView.as_view(template_name='contas/password_change_done.html'),
        name='password_change_done',
    ),
    path('minha-conta/exportar/', views.account_export, name='account_export'),
    path('minha-conta/excluir/', views.account_delete, name='account_delete'),
    path('conta-excluida/', views.account_deleted, name='account_deleted'),

    # --- Esqueci a senha (decisão 74) ---------------------------------------
    # 1) formulário do e-mail  2) "se houver conta, enviamos"  3) link do
    # e-mail com a nova senha  4) "senha alterada". Os nomes das rotas são os
    # que as views do Django procuram sozinhas.
    path(
        'senha/esqueci/',
        auth_views.PasswordResetView.as_view(
            form_class=ResetForm,
            template_name='contas/password_reset_form.html',
            email_template_name='contas/email/redefinir_senha.txt',
            subject_template_name='contas/email/redefinir_senha_assunto.txt',
        ),
        name='password_reset',
    ),
    path(
        'senha/enviado/',
        auth_views.PasswordResetDoneView.as_view(template_name='contas/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'senha/nova/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(template_name='contas/password_reset_confirm.html'),
        name='password_reset_confirm',
    ),
    path(
        'senha/alterada/',
        auth_views.PasswordResetCompleteView.as_view(template_name='contas/password_reset_complete.html'),
        name='password_reset_complete',
    ),
]
