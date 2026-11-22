"""Formulários de conta: cadastro, login e os do admin.

Todos herdam dos formulários prontos do Django (django.contrib.auth.forms),
que já fazem a parte delicada: conferir as duas senhas, rodar os
validadores de senha (AUTH_PASSWORD_VALIDATORS) e guardar só o hash.
Aqui mudamos só o que é da loja: campos, rótulos e mensagens em português.
"""

from django import forms
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    AuthenticationForm,
    BaseUserCreationForm,
    PasswordResetForm,
    UserChangeForm,
)

from .emails import can_send_email, mark_email_sent
from .models import User


class SignupForm(BaseUserCreationForm):
    """Cadastro da cliente: nome, sobrenome, e-mail, senha, confirmação e aceite dos termos."""

    # Aceite da Política de Privacidade e dos Termos de Uso (decisão 77).
    # BooleanField começa DESMARCADO; required=True faz o formulário recusar
    # o cadastro sem a marcação. Nunca deixe initial=True aqui: aceite
    # "pré-marcado" não vale como manifestação livre (LGPD art. 5º XII).
    # O rótulo com os links fica no template (signup.html).
    accept_terms = forms.BooleanField(
        required=True,
        label='Li e aceito os Termos de Uso e a Política de Privacidade',
        error_messages={
            'required': 'Para criar a conta, é preciso ler e aceitar os Termos de Uso '
                        'e a Política de Privacidade.',
        },
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        labels = {
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'email': 'E-mail',
        }
        # autocomplete ajuda o navegador (e o gerenciador de senhas) a
        # preencher os campos certos.
        widgets = {
            'first_name': forms.TextInput(attrs={'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'autocomplete': 'family-name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
        }

    def __init__(self, *args, **kwargs):
        """Torna nome e sobrenome obrigatórios e põe o cursor no primeiro campo."""
        super().__init__(*args, **kwargs)
        # No modelo, nome e sobrenome são opcionais (blank=True, herdado do
        # AbstractUser). No cadastro do site eles são obrigatórios: servem
        # para cumprimentar a cliente e para identificar o pedido.
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        # O formulário-base põe o foco no e-mail; aqui o primeiro campo é o nome.
        self.fields['email'].widget.attrs.pop('autofocus', None)
        self.fields['first_name'].widget.attrs['autofocus'] = True
        self.fields['password1'].label = 'Senha'
        self.fields['password2'].label = 'Confirme a senha'

    def clean_email(self):
        """Padroniza o e-mail (sem espaços, em minúsculas)."""
        return User.objects.normalize_email(self.cleaned_data.get('email'))

    def validate_unique(self):
        """NÃO confere se o e-mail já existe (decisão 66, atualizada na v2 Etapa 3).

        Um ModelForm normalmente avisa "já existe usuário com este e-mail",
        o que revelaria quem tem conta na loja (enumeração). Aqui essa
        checagem é desligada de propósito: a view `signup` trata o e-mail
        existente sem contar nada na tela (envia um aviso por e-mail).
        O banco continua com `unique=True`, então duplicata nunca é gravada.
        """


class LoginForm(AuthenticationForm):
    """Login por e-mail e senha.

    A mensagem de erro é UMA só para "e-mail não cadastrado" e "senha
    errada" (decisão 66). Se fossem diferentes, alguém poderia testar
    e-mails e descobrir quem é cliente da loja (enumeração de e-mails).
    """

    # O campo se chama "username" porque o AuthenticationForm do Django usa
    # esse nome; o conteúdo é o e-mail (USERNAME_FIELD = 'email').
    username = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={'autofocus': True, 'autocomplete': 'email'}),
    )

    error_messages = {
        'invalid_login': 'E-mail ou senha incorretos. Confira os dados e tente de novo.',
        'inactive': 'Esta conta está desativada.',
    }

    def __init__(self, *args, **kwargs):
        """Só troca o rótulo da senha para português."""
        super().__init__(*args, **kwargs)
        self.fields['password'].label = 'Senha'


class ResetForm(PasswordResetForm):
    """ "Esqueci a senha" com limite de frequência por conta (decisão 74).

    O PasswordResetForm do Django já não revela se o e-mail existe: a
    página seguinte é a mesma nos dois casos, e o e-mail só é enviado
    quando há conta. Aqui só acrescentamos o intervalo mínimo entre e-mails
    (contas/emails.py), contra quem pedisse o reset de outra pessoa sem parar.
    """

    def get_users(self, email):
        """Contas que vão receber o link: as do e-mail, fora do intervalo mínimo."""
        for user in super().get_users(email):
            if can_send_email(user):
                mark_email_sent(user)
                yield user


# ---------------------------------------------------------------------------
# "Minha conta" (v2 Etapa 4)
# ---------------------------------------------------------------------------

class ProfileForm(forms.ModelForm):
    """Corrigir nome e sobrenome (LGPD art. 18 III: correção de dados)."""

    class Meta:
        model = User
        fields = ('first_name', 'last_name')
        labels = {'first_name': 'Nome', 'last_name': 'Sobrenome'}
        widgets = {
            'first_name': forms.TextInput(attrs={'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'autocomplete': 'family-name'}),
        }

    def __init__(self, *args, **kwargs):
        """Nome e sobrenome continuam obrigatórios, como no cadastro."""
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True


class PasswordCheckMixin:
    """Confere a senha atual da conta. Usado antes de ações sensíveis.

    Pedir a senha de novo protege contra quem encontra o computador com a
    conta aberta: sem a senha, não troca o e-mail nem exclui a conta.
    """

    def clean_password(self):
        """Recusa se a senha digitada não for a da conta."""
        password = self.cleaned_data.get('password')
        if not self.user.check_password(password):
            raise forms.ValidationError('Senha incorreta.')
        return password


class EmailChangeForm(PasswordCheckMixin, forms.Form):
    """Pedido de troca de e-mail: novo endereço + senha atual (decisão 81).

    NÃO avisa se o novo e-mail já tem conta (seria enumeração): esse caso é
    tratado na view, com a mesma resposta na tela.
    """

    new_email = forms.EmailField(
        label='Novo e-mail',
        widget=forms.EmailInput(attrs={'autocomplete': 'email'}),
    )
    password = forms.CharField(
        label='Senha atual',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )

    def __init__(self, user, *args, **kwargs):
        """Recebe a conta logada, para conferir a senha."""
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_new_email(self):
        """Padroniza o e-mail e recusa o mesmo endereço de hoje."""
        email = User.objects.normalize_email(self.cleaned_data.get('new_email'))
        if email == self.user.email:
            raise forms.ValidationError('Este já é o e-mail da sua conta.')
        return email


class DeleteAccountForm(PasswordCheckMixin, forms.Form):
    """Confirmação da exclusão da conta: senha atual + caixa de ciência."""

    password = forms.CharField(
        label='Senha atual',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )
    confirm = forms.BooleanField(
        required=True,
        label='Entendo que a exclusão é definitiva e não pode ser desfeita.',
        error_messages={'required': 'Marque a caixa para confirmar a exclusão.'},
    )

    def __init__(self, user, *args, **kwargs):
        """Recebe a conta logada, para conferir a senha."""
        self.user = user
        super().__init__(*args, **kwargs)


class AdminUserCreateForm(AdminUserCreationForm):
    """Formulário "Adicionar usuário" do admin, com e-mail no lugar do username."""

    class Meta:
        model = User
        fields = ('email',)


class AdminUserChangeForm(UserChangeForm):
    """Formulário de edição de usuário no admin, ligado ao nosso modelo."""

    class Meta:
        model = User
        fields = '__all__'
