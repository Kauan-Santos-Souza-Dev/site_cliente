"""Rotas de conta. Ficam sob /conta/ (ver config/urls.py).

Login e logout usam as views PRONTAS do Django (LoginView e LogoutView),
apenas configuradas aqui. É uma exceção consciente à decisão 20 (views em
função): essas views são revisadas em segurança por muita gente. Elas
validam o "next" contra open redirect, trocam o código da sessão no login e,
no logout, só aceitam POST (decisão 65).
"""

from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

urlpatterns = [
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
    path('cadastro/', views.signup, name='signup'),
]
