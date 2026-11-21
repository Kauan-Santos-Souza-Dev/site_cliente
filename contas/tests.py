"""Testes das contas: cadastro, login, logout e o carrinho atravessando o login.

Cada teste roda num banco de testes vazio, criado e apagado pelo Django.
self.client é um "navegador de mentira": faz requisições sem abrir servidor.
"""

from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import TestCase
from django.urls import reverse

from carrinho.cart import CART_SESSION_KEY
from loja.models import Category, Product, ProductVariant

User = get_user_model()

# Senha que passa em todos os validadores (10+ caracteres, não comum, não só números).
GOOD_PASSWORD = 'Lirio-do-campo-42'

SIGNUP_DATA = {
    'first_name': 'Maria',
    'last_name': 'Souza',
    'email': 'Maria.Souza@Example.com',
    'password1': GOOD_PASSWORD,
    'password2': GOOD_PASSWORD,
}


class UserModelTest(TestCase):
    """O modelo de usuário com login por e-mail."""

    def test_create_user_guarda_email_em_minusculas_e_senha_com_hash(self):
        user = User.objects.create_user(email='  Ana@Example.COM ', password=GOOD_PASSWORD)
        self.assertEqual(user.email, 'ana@example.com')
        # A senha NUNCA fica em texto puro: o campo guarda "algoritmo$...hash".
        self.assertTrue(user.password.startswith('argon2$'))
        self.assertNotIn(GOOD_PASSWORD, user.password)
        self.assertTrue(user.check_password(GOOD_PASSWORD))
        self.assertFalse(user.is_staff)

    def test_create_superuser_por_email(self):
        admin = User.objects.create_superuser(email='dona@example.com', password=GOOD_PASSWORD)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_save_padroniza_email_vindo_de_qualquer_lugar(self):
        # Mesmo quem altera direto no modelo (admin, shell) passa pelo save().
        user = User.objects.create_user(email='bia@example.com', password=GOOD_PASSWORD)
        user.email = 'BIA@EXAMPLE.COM'
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.email, 'bia@example.com')


class SignupTest(TestCase):
    """Página de cadastro (/conta/cadastro/)."""

    url = reverse('signup')

    def test_cadastro_cria_conta_e_ja_entra(self):
        response = self.client.post(self.url, SIGNUP_DATA)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        user = User.objects.get()
        self.assertEqual(user.email, 'maria.souza@example.com')
        self.assertEqual(user.first_name, 'Maria')
        self.assertTrue(user.password.startswith('argon2$'))
        # A conta ficou gravada na sessão = está logada.
        self.assertEqual(int(self.client.session[SESSION_KEY]), user.pk)

    def test_email_repetido_e_recusado_mesmo_com_maiusculas(self):
        User.objects.create_user(email='maria.souza@example.com', password=GOOD_PASSWORD)
        response = self.client.post(self.url, SIGNUP_DATA)  # e-mail com maiúsculas
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Já existe uma conta com este e-mail.')
        self.assertEqual(User.objects.count(), 1)

    def test_nome_e_sobrenome_sao_obrigatorios(self):
        data = {**SIGNUP_DATA, 'first_name': '', 'last_name': ''}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('first_name', form.errors)
        self.assertIn('last_name', form.errors)
        self.assertFalse(User.objects.exists())

    def test_senhas_fracas_sao_recusadas(self):
        weak_passwords = [
            'Curta-1',          # menos de 10 caracteres
            '12345678901',      # só números (e muito comum)
            'password123',      # está na lista de senhas comuns
            # Quase igual ao e-mail. O validador recusa a partir de 70% de
            # semelhança ("maria.souza" sozinha, ~65%, seria aceita).
            'Maria.Souza@Example',
        ]
        for password in weak_passwords:
            with self.subTest(password=password):
                data = {**SIGNUP_DATA, 'password1': password, 'password2': password}
                response = self.client.post(self.url, data)
                self.assertIn('password2', response.context['form'].errors)
        self.assertFalse(User.objects.exists())

    def test_senhas_diferentes_sao_recusadas(self):
        data = {**SIGNUP_DATA, 'password2': GOOD_PASSWORD + 'x'}
        response = self.client.post(self.url, data)
        self.assertIn('password2', response.context['form'].errors)

    def test_next_do_proprio_site_e_respeitado(self):
        response = self.client.post(self.url, {**SIGNUP_DATA, 'next': '/carrinho/'})
        self.assertRedirects(response, '/carrinho/', fetch_redirect_response=False)

    def test_next_para_outro_site_e_ignorado(self):
        # Proteção contra "open redirect": não pode mandar a cliente para fora.
        response = self.client.post(self.url, {**SIGNUP_DATA, 'next': 'https://evil.example/'})
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_csrf_token_no_formulario(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'csrfmiddlewaretoken')


class LoginTest(TestCase):
    """Página de login (/conta/entrar/, LoginView do Django)."""

    url = reverse('login')

    def setUp(self):
        self.user = User.objects.create_user(
            email='cliente@example.com', password=GOOD_PASSWORD, first_name='Clara',
        )

    def login(self, email, password, **extra):
        """Envia o formulário de login."""
        return self.client.post(self.url, {'username': email, 'password': password, **extra})

    def test_login_correto(self):
        response = self.login('cliente@example.com', GOOD_PASSWORD)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)

    def test_login_com_email_em_maiusculas_funciona(self):
        # Funciona por causa do CÓDIGO (UserManager.get_by_natural_key passa
        # o e-mail para minúsculas), não por causa da collation do MySQL.
        response = self.login('  CLIENTE@Example.COM ', GOOD_PASSWORD)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_get_by_natural_key_ignora_maiusculas(self):
        # O mesmo, testado direto no código que o login usa.
        self.assertEqual(User.objects.get_by_natural_key('CLIENTE@EXAMPLE.COM'), self.user)

    def test_erro_igual_para_email_inexistente_e_senha_errada(self):
        # Contra enumeração: a resposta não pode revelar se o e-mail tem conta.
        wrong_password = self.login('cliente@example.com', 'senha-errada-123')
        unknown_email = self.login('ninguem@example.com', 'senha-errada-123')
        self.assertEqual(
            wrong_password.context['form'].non_field_errors(),
            unknown_email.context['form'].non_field_errors(),
        )
        self.assertContains(wrong_password, 'E-mail ou senha incorretos.')
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_conta_desativada_nao_entra(self):
        self.user.is_active = False
        self.user.save()
        response = self.login('cliente@example.com', GOOD_PASSWORD)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_next_para_outro_site_e_ignorado(self):
        response = self.login('cliente@example.com', GOOD_PASSWORD, next='https://evil.example/')
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_menu_mostra_saudacao_e_botao_sair(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Olá, Clara')
        self.assertContains(response, f'action="{reverse("logout")}"')


class LogoutTest(TestCase):
    """Saída da conta (/conta/sair/)."""

    def setUp(self):
        self.user = User.objects.create_user(email='cliente@example.com', password=GOOD_PASSWORD)
        self.client.force_login(self.user)

    def test_logout_por_get_nao_e_permitido(self):
        # Um link ou <img src="/conta/sair/"> em outro site não pode deslogar ninguém.
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 405)
        self.assertIn(SESSION_KEY, self.client.session)

    def test_logout_por_post_sai_e_esvazia_a_sessao(self):
        session = self.client.session
        session[CART_SESSION_KEY] = {'1': 2}
        session.save()
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)
        # Decisão 67: o logout apaga a sessão inteira, inclusive o carrinho
        # (protege quem usa computador compartilhado).
        self.assertNotIn(CART_SESSION_KEY, self.client.session)


class CartSurvivesLoginTest(TestCase):
    """O carrinho montado como visitante continua lá depois de entrar ou se cadastrar."""

    def setUp(self):
        product = Product.objects.create(
            category=Category.objects.get(slug='vestidos'),
            name='Vestido Teste', slug='vestido-teste', price='150.00',
        )
        self.variant = ProductVariant.objects.create(product=product, size='M', stock=5)
        # A visitante (sem conta) coloca 2 peças no carrinho.
        self.client.post(
            reverse('cart_add', args=[product.id]),
            {'variant': self.variant.id, 'quantity': 2},
        )
        self.cart_before = self.client.session[CART_SESSION_KEY]
        self.session_key_before = self.client.session.session_key

    def assert_cart_kept_and_session_key_changed(self):
        """Confere o carrinho e a troca do código da sessão."""
        self.assertEqual(self.client.session[CART_SESSION_KEY], self.cart_before)
        self.assertEqual(self.cart_before, {str(self.variant.id): 2})
        # O código da sessão mudou (contra "session fixation"): quem conhecia
        # o código antigo não "herda" a conta logada.
        self.assertNotEqual(self.client.session.session_key, self.session_key_before)

    def test_carrinho_sobrevive_ao_login(self):
        User.objects.create_user(email='cliente@example.com', password=GOOD_PASSWORD)
        self.client.post(reverse('login'), {'username': 'cliente@example.com', 'password': GOOD_PASSWORD})
        self.assertIn(SESSION_KEY, self.client.session)
        self.assert_cart_kept_and_session_key_changed()

    def test_carrinho_sobrevive_ao_cadastro(self):
        self.client.post(reverse('signup'), SIGNUP_DATA)
        self.assertIn(SESSION_KEY, self.client.session)
        self.assert_cart_kept_and_session_key_changed()


class UserAdminTest(TestCase):
    """Admin de usuários adaptado ao login por e-mail."""

    def setUp(self):
        admin = User.objects.create_superuser(email='dona@example.com', password=GOOD_PASSWORD)
        self.client.force_login(admin)

    def test_lista_e_tela_de_adicionar_abrem(self):
        self.assertEqual(self.client.get(reverse('admin:contas_user_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:contas_user_add')).status_code, 200)

    def test_admin_cria_usuario_por_email(self):
        response = self.client.post(reverse('admin:contas_user_add'), {
            'email': 'Nova@Example.com',
            'usable_password': 'true',
            'password1': GOOD_PASSWORD,
            'password2': GOOD_PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='nova@example.com').exists())
