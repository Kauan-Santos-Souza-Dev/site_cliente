"""Modelo de usuário da loja: a conta da cliente (e da dona, no admin).

Por que um modelo de usuário próprio?
O Django já traz um `User` pronto, que entra pelo "username" (nome de
usuário). Na loja, a cliente entra pelo E-MAIL. O Django permite trocar o
modelo de usuário pela configuração `AUTH_USER_MODEL` (config/settings.py),
mas só sem dor no começo do projeto: depois que as tabelas existem, a troca
exige recriar o banco. Por isso este modelo veio antes de qualquer outra
mudança em models na v2 (decisão 64).

AbstractUser x AbstractBaseUser:
- `AbstractUser` é o `User` do Django inteiro (nome, e-mail, is_staff,
  permissões, datas...), pronto para herdar. Só removemos o username.
- `AbstractBaseUser` traz só senha e último login: teríamos de reescrever
  permissões e o resto. Mais código, sem ganho para nós.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Cria usuários a partir do e-mail (o gerenciador padrão exige username).

    Um "manager" é o `User.objects`: é por ele que o Django busca e cria
    registros. O `createsuperuser` e o login usam os métodos abaixo.
    """

    # Permite que as migrations conheçam este manager.
    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        """Devolve o e-mail sem espaços nas pontas e todo em minúsculas.

        O Django só passa o DOMÍNIO para minúsculas (a parte antes do @ pode,
        em teoria, diferenciar maiúsculas). Na prática nenhum provedor faz
        isso, e tratar "Maria@X.com" e "maria@x.com" como contas diferentes
        só confundiria a cliente. Não dependemos da "collation" do MySQL
        (regra de comparação de texto do banco), que pode mudar de servidor
        para servidor: a regra fica no código.
        """
        return (email or '').strip().lower()

    def get_by_natural_key(self, username):
        """Busca o usuário pelo e-mail no LOGIN, ignorando maiúsculas.

        O Django chama este método ao autenticar (no site e no admin). O nome
        do parâmetro é "username" porque é assim que o Django o chama, mas
        aqui ele contém o e-mail digitado.
        """
        return self.get(email=self.normalize_email(username))

    def _create_user(self, email, password, **extra_fields):
        """Cria e salva um usuário. A senha é guardada como HASH (set_password)."""
        if not email:
            raise ValueError('O e-mail é obrigatório.')
        user = self.model(email=self.normalize_email(email), **extra_fields)
        # set_password NUNCA guarda a senha em si: calcula o hash (Argon2,
        # decisão 63) e guarda só o hash.
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Cria uma conta comum de cliente (sem acesso ao admin)."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Cria a conta de administração (usado pelo `createsuperuser`)."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        # Conta criada no servidor por quem administra: e-mail já conhecido.
        extra_fields.setdefault('email_verified', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('O superusuário precisa de is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('O superusuário precisa de is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Conta de usuário da loja, com login por e-mail."""

    # Tira o campo "username" herdado do AbstractUser.
    username = None
    # unique=True: o banco recusa dois usuários com o mesmo e-mail.
    email = models.EmailField('e-mail', unique=True)
    # A cliente provou que o e-mail é dela (clicou no link de verificação).
    # Só com isso ela pode finalizar uma compra (decisão 72).
    email_verified = models.BooleanField('e-mail verificado', default=False)
    # Quando enviamos o último e-mail de segurança (verificação, aviso de
    # cadastro ou redefinição de senha). Serve para limitar a frequência e
    # evitar que alguém "bombardeie" a caixa de entrada de outra pessoa.
    # Fica no banco (não no cache) para valer em todos os processos.
    last_email_sent_at = models.DateTimeField('último e-mail enviado em', null=True, blank=True)
    # Quando a conta foi excluída pela cliente (decisão 78). "Excluir" aqui
    # é ANONIMIZAR: os dados pessoais somem, mas a linha fica, para que os
    # pedidos (Etapa 5) continuem apontando para ela pelo prazo legal.
    anonymized_at = models.DateTimeField('anonimizada em', null=True, blank=True)

    # Campo usado como "nome de login" pelo Django (login, admin, createsuperuser).
    USERNAME_FIELD = 'email'
    # Campos extras que o `createsuperuser` pergunta. O e-mail e a senha já
    # são pedidos sempre, então não há mais nenhum.
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'

    def __str__(self):
        """Mostra o e-mail (no admin e no shell)."""
        return self.email

    def save(self, *args, **kwargs):
        """Guarda o e-mail sempre em minúsculas, venha de onde vier (site, admin, shell)."""
        self.email = User.objects.normalize_email(self.email)
        super().save(*args, **kwargs)


class Consent(models.Model):
    """Registro do aceite da Política de Privacidade e dos Termos de Uso (decisão 77).

    Uma linha por aceite: QUEM aceitou, QUAIS versões dos textos e QUANDO.
    A LGPD (art. 8º, § 2º) diz que cabe à loja provar o aceite; esta tabela
    é essa prova. Não guardamos IP nem navegador: não são necessários para
    provar o aceite (minimização, art. 6º III).

    A base legal para guardar os dados da conta é a execução do contrato
    (art. 7º V). A caixa do cadastro registra que a cliente LEU e ACEITOU
    versões específicas dos textos.
    """

    # CASCADE: se a conta for apagada de verdade (só contas nunca verificadas,
    # decisão 79), o aceite vai junto. Na exclusão pedida pela cliente a conta
    # é anonimizada, não apagada, e o aceite continua como prova.
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='consents', verbose_name='usuário'
    )
    privacy_policy_version = models.CharField('versão da Política de Privacidade', max_length=20)
    terms_version = models.CharField('versão dos Termos de Uso', max_length=20)
    accepted_at = models.DateTimeField('aceito em', auto_now_add=True)

    class Meta:
        verbose_name = 'aceite de termos'
        verbose_name_plural = 'aceites de termos'
        ordering = ['-accepted_at']

    def __str__(self):
        """Ex.: "Política 2026-11-22 / Termos 2026-11-22"."""
        return f'Política {self.privacy_policy_version} / Termos {self.terms_version}'
