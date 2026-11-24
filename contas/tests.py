"""Testes das contas: cadastro, verificação de e-mail, login, bloqueio de
tentativas, redefinição de senha, 2FA do admin, grupo de permissões e,
desde a v2 Etapa 4, LGPD (aceite, Minha conta, exportar, excluir/anonimizar,
limpeza de dados antigos, páginas legais e aviso de cookies).

Cada teste roda num banco de testes vazio, criado e apagado pelo Django.
self.client é um "navegador de mentira": faz requisições sem abrir servidor.
Os e-mails não saem de verdade: nos testes o Django os guarda em
`mail.outbox`, uma lista que podemos conferir.
"""

import io
import json
import re
import time
from datetime import timedelta
from unittest import mock

from axes.models import AccessAttempt, AccessLog
from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from carrinho.cart import CART_SESSION_KEY
from loja.models import Category, Product, ProductVariant
from pedidos.models import Order

from .legal import ORDER_RETENTION, PRIVACY_POLICY_VERSION, TERMS_VERSION
from .models import Consent
from .test_utils import GOOD_PASSWORD, login_admin, make_customer, make_order, make_variant
from .tokens import make_email_change_token, make_verification_token

User = get_user_model()

SIGNUP_DATA = {
    'first_name': 'Maria',
    'last_name': 'Souza',
    'email': 'Maria.Souza@Example.com',
    'password1': GOOD_PASSWORD,
    'password2': GOOD_PASSWORD,
    # Caixa de aceite dos Termos e da Política (v2 Etapa 4). Um checkbox
    # marcado chega ao servidor como "on".
    'accept_terms': 'on',
}


def find_link(message):
    """Acha o primeiro link (http...) no corpo de um e-mail."""
    return re.search(r'https?://\S+', message.body).group(0)


def link_path(url):
    """Tira "http://testserver" do link, deixando só o caminho para o client."""
    return url.replace('http://testserver', '')


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
        # Conta de cliente começa sem e-mail verificado.
        self.assertFalse(user.email_verified)

    def test_create_superuser_por_email_ja_verificado(self):
        admin = User.objects.create_superuser(email='dona@example.com', password=GOOD_PASSWORD)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.email_verified)

    def test_save_padroniza_email_vindo_de_qualquer_lugar(self):
        # Mesmo quem altera direto no modelo (admin, shell) passa pelo save().
        user = User.objects.create_user(email='bia@example.com', password=GOOD_PASSWORD)
        user.email = 'BIA@EXAMPLE.COM'
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.email, 'bia@example.com')


class SignupTest(TestCase):
    """Cadastro (/conta/cadastro/): resposta genérica, sem login automático."""

    url = reverse('signup')

    def test_email_novo_cria_conta_nao_verificada_sem_login(self):
        response = self.client.post(self.url, SIGNUP_DATA)
        self.assertRedirects(response, reverse('signup_done'))
        user = User.objects.get()
        self.assertEqual(user.email, 'maria.souza@example.com')
        self.assertTrue(user.password.startswith('argon2$'))
        self.assertFalse(user.email_verified)
        # Decisão 73: NÃO entra logada. A conta só vale depois do link.
        self.assertNotIn(SESSION_KEY, self.client.session)
        # Um e-mail com o link de verificação, para o endereço cadastrado.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['maria.souza@example.com'])
        self.assertIn('/conta/verificar/', mail.outbox[0].body)

    def test_resposta_identica_para_email_novo_e_existente(self):
        # Contra enumeração: quem cadastra não pode descobrir se o e-mail tem conta.
        # Cada caso usa um "navegador" novo e segue o redirecionamento até o fim.
        new = Client().post(self.url, SIGNUP_DATA, follow=True)

        User.objects.filter(email='maria.souza@example.com').update(email_verified=True)
        verified = Client().post(self.url, SIGNUP_DATA, follow=True)

        User.objects.update(email_verified=False, last_email_sent_at=None)
        unverified = Client().post(self.url, SIGNUP_DATA, follow=True)

        for response in (verified, unverified):
            self.assertEqual(response.redirect_chain, new.redirect_chain)
            self.assertEqual(response.status_code, new.status_code)
            self.assertEqual(response.content, new.content)

    def test_email_de_conta_verificada_recebe_aviso_e_nada_muda(self):
        user = make_customer(email='maria.souza@example.com', first_name='Maria')
        old_password_hash = user.password
        self.client.post(self.url, {**SIGNUP_DATA, 'password1': 'Outra-senha-99', 'password2': 'Outra-senha-99'})
        user.refresh_from_db()
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.password, old_password_hash)  # senha intacta
        self.assertNotIn(SESSION_KEY, self.client.session)
        # A dona do e-mail recebe um aviso (não um link de verificação).
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Tentativa de cadastro', mail.outbox[0].subject)
        self.assertNotIn('/conta/verificar/', mail.outbox[0].body)

    def test_conta_nao_verificada_tem_senha_substituida(self):
        # Pré-sequestro: o "atacante" cadastra o e-mail da vítima com a senha dele.
        attacker_password = 'Senha-do-atacante-1'
        User.objects.create_user(email='maria.souza@example.com', password=attacker_password)

        # A vítima se cadastra depois: o cadastro novo substitui nome e senha.
        self.client.post(self.url, SIGNUP_DATA)
        user = User.objects.get()
        self.assertFalse(user.check_password(attacker_password))
        self.assertTrue(user.check_password(GOOD_PASSWORD))
        self.assertEqual(user.first_name, 'Maria')
        # E recebe um link novo de verificação.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/conta/verificar/', mail.outbox[0].body)

    def test_cadastros_seguidos_respeitam_o_intervalo_de_emails(self):
        # Contra "mail bombing": repetir o cadastro não dispara um e-mail por vez.
        self.client.post(self.url, SIGNUP_DATA)
        self.client.post(self.url, SIGNUP_DATA)
        self.client.post(self.url, SIGNUP_DATA)
        self.assertEqual(len(mail.outbox), 1)

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

    def test_formulario_nao_avisa_email_repetido(self):
        make_customer(email='maria.souza@example.com')
        response = self.client.post(self.url, {**SIGNUP_DATA, 'password2': 'diferente-123'})
        # Com outro erro no formulário, a página volta, mas sem falar do e-mail.
        self.assertNotIn('email', response.context['form'].errors)

    def test_csrf_token_no_formulario(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'csrfmiddlewaretoken')


class EmailVerificationTest(TestCase):
    """Link de verificação (/conta/verificar/<token>/) e reenvio."""

    def setUp(self):
        self.user = make_customer(email='cliente@example.com', verified=False, first_name='Clara')

    def test_link_do_email_verifica_a_conta(self):
        Client().post(reverse('signup'), SIGNUP_DATA)
        response = self.client.get(link_path(find_link(mail.outbox[0])))
        self.assertContains(response, 'E-mail confirmado')
        self.assertTrue(User.objects.get(email='maria.souza@example.com').email_verified)

    def test_abrir_o_link_duas_vezes_nao_faz_mal(self):
        url = reverse('verify_email', args=[make_verification_token(self.user)])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_token_adulterado_e_recusado(self):
        token = make_verification_token(self.user)
        tampered = token[:-2] + ('AA' if not token.endswith('AA') else 'BB')
        response = self.client.get(reverse('verify_email', args=[tampered]))
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_link_vencido_depois_de_24_horas(self):
        token = make_verification_token(self.user)
        # Finge que o relógio andou 24 h + 1 s (a assinatura guarda a hora de criação).
        later = time.time() + 24 * 60 * 60 + 1
        with mock.patch('django.core.signing.time.time', return_value=later):
            response = self.client.get(reverse('verify_email', args=[token]))
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_link_antigo_nao_vale_se_o_email_mudou(self):
        token = make_verification_token(self.user)
        self.user.email = 'novo@example.com'
        self.user.save()
        response = self.client.get(reverse('verify_email', args=[token]))
        self.assertEqual(response.status_code, 400)

    def test_reenvio_respeita_o_intervalo(self):
        self.client.force_login(self.user)
        self.client.post(reverse('resend_verification'))
        response = self.client.post(reverse('resend_verification'), follow=True)
        # Dois pedidos seguidos = um e-mail só, e a mesma mensagem na tela.
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(response, 'Se for possível, enviamos um novo link')

    def test_reenvio_libera_depois_do_intervalo(self):
        self.client.force_login(self.user)
        self.client.post(reverse('resend_verification'))
        User.objects.update(last_email_sent_at=timezone.now() - timedelta(minutes=3))
        self.client.post(reverse('resend_verification'))
        self.assertEqual(len(mail.outbox), 2)

    def test_reenvio_so_por_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('resend_verification')).status_code, 405)


class CheckoutGateTest(TestCase):
    """O checkout exige login E e-mail verificado (decisão 72)."""

    url = reverse('checkout')

    def test_visitante_vai_para_o_login_com_next(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}", fetch_redirect_response=False)

    def test_conta_nao_verificada_vai_para_a_pagina_pendente(self):
        self.client.force_login(make_customer(verified=False))
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('verification_pending'))

    def test_conta_verificada_passa(self):
        self.client.force_login(make_customer())
        response = self.client.get(self.url)
        # Passou pela checagem; como o carrinho está vazio, o checkout manda ao carrinho.
        self.assertRedirects(response, reverse('cart_detail'), fetch_redirect_response=False)


class LoginTest(TestCase):
    """Página de login (/conta/entrar/, LoginView do Django)."""

    url = reverse('login')

    def setUp(self):
        self.user = make_customer(first_name='Clara')

    def login(self, email, password, **extra):
        """Envia o formulário de login."""
        return self.client.post(self.url, {'username': email, 'password': password, **extra})

    def test_login_correto(self):
        response = self.login('cliente@example.com', GOOD_PASSWORD)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)

    def test_conta_nao_verificada_tambem_entra(self):
        # Pode entrar e montar o carrinho; só não finaliza a compra.
        make_customer(email='nova@example.com', verified=False)
        response = self.login('nova@example.com', GOOD_PASSWORD)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_login_com_email_em_maiusculas_funciona(self):
        # Funciona por causa do CÓDIGO (UserManager.get_by_natural_key passa
        # o e-mail para minúsculas), não por causa da collation do MySQL.
        response = self.login('  CLIENTE@Example.COM ', GOOD_PASSWORD)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_get_by_natural_key_ignora_maiusculas(self):
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


class LoginLockoutTest(TestCase):
    """Bloqueio de tentativas com django-axes: 5 erros, 15 minutos, e-mail + IP."""

    url = reverse('login')

    def setUp(self):
        self.user = make_customer()

    def login(self, email, password, client=None):
        """Tenta entrar (por padrão, com o client do teste)."""
        client = client or self.client
        return client.post(self.url, {'username': email, 'password': password})

    def fail(self, email, times, client=None):
        """Erra a senha `times` vezes seguidas."""
        for _ in range(times):
            self.login(email, 'senha-errada-123', client)

    def test_cinco_erros_bloqueiam_ate_a_senha_certa(self):
        self.fail('cliente@example.com', 5)
        response = self.login('cliente@example.com', GOOD_PASSWORD)
        # 429 = "muitas requisições". Nem a senha certa entra durante o bloqueio.
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, 'Muitas tentativas', status_code=429)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_quatro_erros_ainda_deixam_entrar(self):
        self.fail('cliente@example.com', 4)
        response = self.login('cliente@example.com', GOOD_PASSWORD)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_bloqueio_nao_revela_se_o_email_existe(self):
        # Mesmo bloqueio, mesma página, para e-mail cadastrado e inexistente.
        self.fail('cliente@example.com', 5)
        existing = self.login('cliente@example.com', 'senha-errada-123')
        self.fail('ninguem@example.com', 5)
        unknown = self.login('ninguem@example.com', 'senha-errada-123')
        self.assertEqual(existing.status_code, 429)
        self.assertEqual(unknown.status_code, existing.status_code)
        self.assertEqual(unknown.content, existing.content)
        self.assertNotIn(b'cliente@example.com', existing.content)

    def test_maiusculas_contam_no_mesmo_contador(self):
        # Sem a padronização (contas/axes.py) cada variação teria 5 tentativas novas.
        for email in ['cliente@example.com', 'CLIENTE@example.com', 'Cliente@Example.com',
                      ' cliente@EXAMPLE.com', 'CLIENTE@EXAMPLE.COM']:
            self.login(email, 'senha-errada-123')
        response = self.login('cliente@example.com', GOOD_PASSWORD)
        self.assertEqual(response.status_code, 429)

    def test_outro_ip_nao_e_bloqueado(self):
        # O bloqueio é do par e-mail + IP: um atacante não trava a conta de quem
        # está em outro lugar.
        self.fail('cliente@example.com', 5)
        other_place = Client(REMOTE_ADDR='10.0.0.9')
        response = self.login('cliente@example.com', GOOD_PASSWORD, other_place)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_bloqueio_acaba_depois_de_15_minutos(self):
        self.fail('cliente@example.com', 5)
        # Finge que as tentativas aconteceram há 16 minutos.
        AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(minutes=16))
        response = self.login('cliente@example.com', GOOD_PASSWORD)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_login_certo_zera_o_contador(self):
        self.fail('cliente@example.com', 4)
        self.login('cliente@example.com', GOOD_PASSWORD)
        self.client.post(reverse('logout'))
        self.fail('cliente@example.com', 4)  # 4 novos erros: ainda não bloqueia
        response = self.login('cliente@example.com', GOOD_PASSWORD)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_admin_tambem_e_protegido(self):
        make_customer(email='dona@example.com', is_staff=True)
        for _ in range(5):
            self.client.post(reverse('admin:login'), {'username': 'dona@example.com', 'password': 'errada-12345'})
        response = self.client.post(reverse('admin:login'), {'username': 'dona@example.com', 'password': 'errada-12345'})
        self.assertEqual(response.status_code, 429)


class LogoutTest(TestCase):
    """Saída da conta (/conta/sair/)."""

    def setUp(self):
        self.client.force_login(make_customer())

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
        # Decisão 67: o logout apaga a sessão inteira, inclusive o carrinho.
        self.assertNotIn(CART_SESSION_KEY, self.client.session)


class CartSurvivesLoginTest(TestCase):
    """O carrinho montado como visitante continua lá no cadastro e no login."""

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
        self.expected_cart = {str(self.variant.id): 2}
        self.session_key_before = self.client.session.session_key

    def test_carrinho_sobrevive_ao_login(self):
        make_customer()
        self.client.post(reverse('login'), {'username': 'cliente@example.com', 'password': GOOD_PASSWORD})
        self.assertIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.client.session[CART_SESSION_KEY], self.expected_cart)
        # O código da sessão mudou (contra "session fixation"): quem conhecia
        # o código antigo não "herda" a conta logada.
        self.assertNotEqual(self.client.session.session_key, self.session_key_before)

    def test_carrinho_sobrevive_ao_cadastro_verificacao_e_login(self):
        # 1) Cadastro: sem login, a sessão (e o carrinho) ficam como estavam.
        self.client.post(reverse('signup'), SIGNUP_DATA)
        self.assertEqual(self.client.session[CART_SESSION_KEY], self.expected_cart)
        # 2) Abre o link do e-mail no mesmo aparelho.
        self.client.get(link_path(find_link(mail.outbox[0])))
        self.assertEqual(self.client.session[CART_SESSION_KEY], self.expected_cart)
        # 3) Entra: o carrinho continua lá e já dá para ir ao checkout.
        self.client.post(reverse('login'), {'username': SIGNUP_DATA['email'], 'password': GOOD_PASSWORD})
        self.assertEqual(self.client.session[CART_SESSION_KEY], self.expected_cart)
        self.assertEqual(self.client.get(reverse('checkout')).status_code, 200)


class PasswordResetTest(TestCase):
    """Esqueci a senha (views prontas do Django + ResetForm)."""

    url = reverse('password_reset')

    def setUp(self):
        self.user = make_customer()

    def test_link_valido_por_1_hora(self):
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 60 * 60)

    def test_resposta_igual_exista_o_email_ou_nao(self):
        existing = Client().post(self.url, {'email': 'cliente@example.com'}, follow=True)
        unknown = Client().post(self.url, {'email': 'ninguem@example.com'}, follow=True)
        self.assertEqual(existing.redirect_chain, unknown.redirect_chain)
        self.assertEqual(existing.content, unknown.content)
        # Só a conta que existe recebe e-mail.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['cliente@example.com'])

    def test_redefinir_troca_a_senha_e_o_link_so_vale_uma_vez(self):
        self.client.post(self.url, {'email': 'cliente@example.com'})
        link = link_path(find_link(mail.outbox[0]))
        # O Django troca o token da URL por um marcador e guarda o token na
        # sessão (para ele não vazar pelo cabeçalho Referer). Seguimos o redirect.
        page = self.client.get(link, follow=True)
        form_url = page.redirect_chain[-1][0]
        new_password = 'Nova-senha-segura-7'
        self.client.post(form_url, {'new_password1': new_password, 'new_password2': new_password})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.check_password(GOOD_PASSWORD))
        # O mesmo link não funciona de novo (o token depende do hash da senha antiga).
        again = Client().get(link, follow=True)
        self.assertFalse(again.context['validlink'])

    def test_pedidos_seguidos_respeitam_o_intervalo(self):
        self.client.post(self.url, {'email': 'cliente@example.com'})
        self.client.post(self.url, {'email': 'cliente@example.com'})
        self.assertEqual(len(mail.outbox), 1)


class AdminTwoFactorTest(TestCase):
    """2FA obrigatório no admin (django-otp) e o comando configurar_2fa."""

    def setUp(self):
        self.admin = User.objects.create_superuser(email='dona@example.com', password=GOOD_PASSWORD)

    def admin_login(self, otp_token, device=None, client=None):
        """Envia o formulário de login do admin: e-mail, senha, dispositivo e código.

        O django-otp exige escolher o dispositivo ("Celular" ou "Códigos de
        backup"): testar o código em todos registraria falhas nos outros.
        """
        client = client or self.client
        data = {'username': 'dona@example.com', 'password': GOOD_PASSWORD, 'otp_token': otp_token}
        if device is not None:
            data['otp_device'] = device.persistent_id
        return client.post(reverse('admin:login'), data)

    def configure(self, *extra):
        """Roda o comando e devolve o que ele imprimiu."""
        out = io.StringIO()
        call_command('configurar_2fa', 'dona@example.com', *extra, stdout=out)
        return out.getvalue()

    def backup_codes(self):
        """Os códigos de backup da dona, lidos do banco."""
        return list(StaticToken.objects.filter(device__user=self.admin).values_list('token', flat=True))

    def test_senha_certa_sem_2fa_nao_entra(self):
        # force_login = senha certa. Sem o segundo fator, o admin não abre.
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin:index'))
        self.assertRedirects(response, f"{reverse('admin:login')}?next={reverse('admin:index')}")

    def test_com_2fa_entra(self):
        login_admin(self.client, self.admin)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)

    def test_login_com_codigo_do_app_autenticador(self):
        self.configure()
        device = TOTPDevice.objects.get(user=self.admin)
        # Calcula o código do momento, exatamente como o celular faria.
        code = f'{totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits):06d}'
        response = self.admin_login(code, device)
        self.assertEqual(response.status_code, 302)  # login aceito
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)

    def test_login_sem_codigo_ou_com_codigo_errado_falha(self):
        self.configure()
        device = TOTPDevice.objects.get(user=self.admin)
        self.assertEqual(self.admin_login('', device).status_code, 200)        # volta ao formulário
        self.assertEqual(self.admin_login('000000', device).status_code, 200)
        self.assertEqual(self.admin_login('000000').status_code, 200)          # sem escolher dispositivo
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)

    def test_codigo_de_backup_funciona_uma_vez(self):
        self.configure()
        device = StaticDevice.objects.get(user=self.admin)
        code = self.backup_codes()[0]
        browser = Client()
        first = self.admin_login(code, device, browser)
        self.assertEqual(first.status_code, 302)  # login aceito
        self.assertEqual(browser.get(reverse('admin:index')).status_code, 200)
        second = self.admin_login(code, device, Client())
        self.assertEqual(second.status_code, 200)  # recusado: o código já foi usado

    def test_comando_cria_app_autenticador_e_10_codigos(self):
        output = self.configure()
        self.assertTrue(TOTPDevice.objects.filter(user=self.admin, confirmed=True).exists())
        codes = self.backup_codes()
        self.assertEqual(len(codes), 10)
        self.assertIn('otpauth://totp/', output)
        for code in codes:
            self.assertIn(code, output)

    def test_saida_do_comando_funciona_no_terminal_do_windows(self):
        # Bug real: os caracteres de bloco do QR (█ ▀ ▄) quebravam no terminal
        # do Windows (codificação cp1252), DEPOIS de o 2FA já ter sido gravado.
        output = self.configure()
        output.encode('cp1252')  # não pode lançar UnicodeEncodeError

    def test_comando_nao_sobrescreve_sem_redefinir(self):
        self.configure()
        with self.assertRaises(CommandError):
            self.configure()

    def test_redefinir_troca_dispositivo_e_codigos(self):
        self.configure()
        old_device = TOTPDevice.objects.get(user=self.admin).pk
        old_codes = set(self.backup_codes())
        self.configure('--redefinir')
        self.assertNotEqual(TOTPDevice.objects.get(user=self.admin).pk, old_device)
        self.assertEqual(StaticDevice.objects.filter(user=self.admin).count(), 1)
        self.assertFalse(old_codes & set(self.backup_codes()))

    def test_comando_recusa_conta_de_cliente(self):
        make_customer()
        with self.assertRaises(CommandError):
            call_command('configurar_2fa', 'cliente@example.com', stdout=io.StringIO())


class UserAdminTest(TestCase):
    """Admin de usuários adaptado ao login por e-mail."""

    def setUp(self):
        admin = User.objects.create_superuser(email='dona@example.com', password=GOOD_PASSWORD)
        login_admin(self.client, admin)

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


class GroupsCommandTest(TestCase):
    """Comando criar_grupos: grupo "Loja" sem acesso aos dados de contas."""

    def run_command(self):
        """Roda o comando sem imprimir no terminal dos testes."""
        call_command('criar_grupos', stdout=io.StringIO())

    def test_cria_grupo_com_catalogo_e_pedidos(self):
        self.run_command()
        codenames = set(Group.objects.get(name='Loja').permissions.values_list('codename', flat=True))
        self.assertIn('change_product', codenames)
        self.assertIn('change_order', codenames)
        self.assertNotIn('add_category', codenames)  # categorias são fixas

    def test_grupo_nao_ve_contas_nem_seguranca(self):
        self.run_command()
        apps = set(
            Group.objects.get(name='Loja').permissions.values_list('content_type__app_label', flat=True)
        )
        # pagamentos (v2 Etapa 7): só "view" (decisão 102).
        self.assertEqual(apps, {'loja', 'pedidos', 'pagamentos'})

    def test_rodar_de_novo_nao_duplica(self):
        self.run_command()
        self.run_command()
        self.assertEqual(Group.objects.filter(name='Loja').count(), 1)
        self.assertEqual(Group.objects.get(name='Loja').permissions.count(), 24)  # 23 + ver pagamentos

    def test_conta_do_grupo_edita_produtos_mas_nao_ve_clientes(self):
        self.run_command()
        staff = make_customer(email='equipe@example.com', is_staff=True)
        staff.groups.add(Group.objects.get(name='Loja'))
        login_admin(self.client, staff)
        self.assertEqual(self.client.get(reverse('admin:loja_product_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:contas_user_changelist')).status_code, 403)


# ===========================================================================
# v2 Etapa 4 — LGPD
# ===========================================================================

class ConsentSignupTest(TestCase):
    """Aceite dos Termos e da Política no cadastro (decisão 77)."""

    def test_caixa_vem_desmarcada(self):
        response = self.client.get(reverse('signup'))
        # Acha a tag <input ... name="accept_terms" ...> e confere que não tem "checked".
        tag = re.search(r'<input[^>]*name="accept_terms"[^>]*>', response.content.decode()).group(0)
        self.assertIn('type="checkbox"', tag)
        self.assertNotIn('checked', tag)

    def test_sem_marcar_a_caixa_nao_cria_conta(self):
        data = {**SIGNUP_DATA}
        del data['accept_terms']  # checkbox desmarcado simplesmente não é enviado
        response = self.client.post(reverse('signup'), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'é preciso ler e aceitar os Termos de Uso')
        self.assertFalse(User.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_marcando_grava_versoes_e_data_do_aceite(self):
        before = timezone.now()
        self.client.post(reverse('signup'), SIGNUP_DATA)
        user = User.objects.get(email='maria.souza@example.com')
        consent = Consent.objects.get(user=user)
        self.assertEqual(consent.privacy_policy_version, PRIVACY_POLICY_VERSION)
        self.assertEqual(consent.terms_version, TERMS_VERSION)
        self.assertGreaterEqual(consent.accepted_at, before)

    def test_cadastro_refeito_em_conta_nao_verificada_grava_novo_aceite(self):
        make_customer(email='maria.souza@example.com', verified=False)
        self.client.post(reverse('signup'), SIGNUP_DATA)
        self.assertEqual(Consent.objects.count(), 1)

    def test_conta_verificada_nao_ganha_aceite_e_resposta_e_a_mesma(self):
        make_customer(email='maria.souza@example.com', verified=True)
        response = self.client.post(reverse('signup'), SIGNUP_DATA)
        self.assertRedirects(response, reverse('signup_done'))
        self.assertFalse(Consent.objects.exists())


class AccountPageTest(TestCase):
    """Página "Minha conta": login obrigatório e só a PRÓPRIA conta."""

    def setUp(self):
        self.user = make_customer(first_name='Clara', last_name='Lima')
        self.other = make_customer(email='outra@example.com', first_name='Joana', last_name='Reis')

    def test_todas_as_paginas_exigem_login(self):
        names = ['account', 'account_edit', 'email_change', 'password_change', 'account_delete']
        for name in names:
            with self.subTest(pagina=name):
                response = self.client.get(reverse(name))
                self.assertRedirects(response, f"{reverse('login')}?next={reverse(name)}")
        # A exportação é por POST; sem login também vai para o login.
        response = self.client.post(reverse('account_export'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_mostra_os_dados_da_propria_conta_e_nao_os_de_outra(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('account'))
        self.assertContains(response, 'cliente@example.com')
        self.assertContains(response, 'Clara Lima')
        self.assertNotContains(response, 'outra@example.com')

    def test_corrigir_nome(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('account_edit'), {'first_name': 'Clarice', 'last_name': 'Lima'}, follow=True
        )
        self.assertContains(response, 'Seus dados foram atualizados')
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Clarice')

    def test_editar_ignora_campos_que_nao_estao_no_formulario(self):
        # Mesmo que alguém envie "email" ou "is_staff" à mão, o ModelForm só
        # usa os campos declarados (nome e sobrenome). Nada de virar admin.
        self.client.force_login(self.user)
        self.client.post(reverse('account_edit'), {
            'first_name': 'Clara', 'last_name': 'Lima',
            'email': 'hacker@example.com', 'is_staff': 'on',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'cliente@example.com')
        self.assertFalse(self.user.is_staff)

    def test_trocar_senha_pede_a_senha_atual(self):
        self.client.force_login(self.user)
        new_password = 'Rosa-de-Saron-77'
        self.client.post(reverse('password_change'), {
            'old_password': 'senha-errada-123',
            'new_password1': new_password, 'new_password2': new_password,
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(GOOD_PASSWORD))
        self.client.post(reverse('password_change'), {
            'old_password': GOOD_PASSWORD,
            'new_password1': new_password, 'new_password2': new_password,
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))


class EmailChangeTest(TestCase):
    """Troca de e-mail com link enviado ao NOVO endereço (decisão 81)."""

    def setUp(self):
        self.user = make_customer(first_name='Clara')
        self.client.force_login(self.user)

    def ask(self, new_email, password=GOOD_PASSWORD):
        """Pede a troca de e-mail e segue o redirecionamento."""
        return self.client.post(
            reverse('email_change'), {'new_email': new_email, 'password': password}, follow=True
        )

    def test_senha_errada_nao_envia_nada(self):
        response = self.ask('nova@example.com', password='senha-errada-123')
        self.assertContains(response, 'Senha incorreta')
        self.assertEqual(len(mail.outbox), 0)

    def test_fluxo_completo_troca_o_email_e_avisa_o_antigo(self):
        response = self.ask('Nova@Example.com')
        self.assertContains(response, 'Se for possível usar este endereço')
        # O e-mail ainda NÃO mudou: só muda com o clique no link.
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'cliente@example.com')
        self.assertEqual(mail.outbox[0].to, ['nova@example.com'])

        response = self.client.get(link_path(find_link(mail.outbox[0])))
        self.assertContains(response, 'E-mail alterado')
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'nova@example.com')
        self.assertTrue(self.user.email_verified)
        # Aviso de segurança no endereço antigo.
        self.assertEqual(mail.outbox[1].to, ['cliente@example.com'])

    def test_email_ja_usado_tem_a_mesma_resposta_e_nao_troca(self):
        make_customer(email='ocupado@example.com', first_name='Joana')
        response = self.ask('ocupado@example.com')
        # Mesma mensagem do caso normal: quem pede não descobre que o e-mail existe.
        self.assertContains(response, 'Se for possível usar este endereço')
        # Quem recebe é a DONA do e-mail ocupado, com o aviso de "conta existente",
        # sem link de troca.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ocupado@example.com'])
        self.assertNotIn('/minha-conta/email/confirmar/', mail.outbox[0].body)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'cliente@example.com')

    def test_link_so_vale_uma_vez(self):
        self.ask('nova@example.com')
        url = link_path(find_link(mail.outbox[0]))
        self.assertEqual(self.client.get(url).status_code, 200)
        # Na segunda vez, o e-mail "antigo" do token já não é o da conta.
        self.assertEqual(self.client.get(url).status_code, 400)

    def test_token_adulterado_e_recusado(self):
        self.ask('nova@example.com')
        url = link_path(find_link(mail.outbox[0])).rstrip('/')
        tampered = url[:-2] + ('AA' if not url.endswith('AA') else 'BB') + '/'
        self.assertEqual(self.client.get(tampered).status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'cliente@example.com')

    def test_link_vencido_depois_de_24_horas(self):
        token = make_email_change_token(self.user, 'nova@example.com')
        later = time.time() + 24 * 60 * 60 + 1
        with mock.patch('django.core.signing.time.time', return_value=later):
            response = self.client.get(reverse('email_change_confirm', args=[token]))
        self.assertEqual(response.status_code, 400)

    def test_email_ocupado_depois_do_envio_nao_troca(self):
        token = make_email_change_token(self.user, 'nova@example.com')
        make_customer(email='nova@example.com')
        response = self.client.get(reverse('email_change_confirm', args=[token]))
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'cliente@example.com')


class ExportDataTest(TestCase):
    """Exportar os dados da conta em JSON (LGPD art. 18 II e V)."""

    def setUp(self):
        self.user = make_customer(first_name='Clara', last_name='Lima')
        Consent.objects.create(user=self.user, privacy_policy_version='v1', terms_version='v1')
        make_customer(email='outra@example.com')
        self.client.force_login(self.user)

    def test_so_por_post(self):
        self.assertEqual(self.client.get(reverse('account_export')).status_code, 405)

    def test_baixa_json_com_os_dados_da_propria_conta(self):
        response = self.client.post(reverse('account_export'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['conta']['email'], 'cliente@example.com')
        self.assertEqual(data['conta']['nome'], 'Clara')
        self.assertEqual(data['aceites'][0]['politica_de_privacidade'], 'v1')
        content = response.content.decode('utf-8')
        # Nem o hash da senha nem dados de outra conta.
        self.assertNotIn('argon2', content)
        self.assertNotIn('outra@example.com', content)


class DeleteAccountTest(TestCase):
    """Excluir a conta = anonimizar (decisão 78)."""

    def setUp(self):
        self.user = make_customer(first_name='Clara', last_name='Lima')
        Consent.objects.create(user=self.user, privacy_policy_version='v1', terms_version='v1')
        self.client.force_login(self.user)

    def delete(self, password=GOOD_PASSWORD, confirm=True):
        """Envia o formulário de exclusão."""
        data = {'password': password}
        if confirm:
            data['confirm'] = 'on'
        return self.client.post(reverse('account_delete'), data)

    def test_senha_errada_nao_exclui(self):
        response = self.delete(password='senha-errada-123')
        self.assertContains(response, 'Senha incorreta')
        self.user.refresh_from_db()
        self.assertIsNone(self.user.anonymized_at)

    def test_sem_marcar_a_confirmacao_nao_exclui(self):
        response = self.delete(confirm=False)
        self.assertContains(response, 'Marque a caixa para confirmar')
        self.user.refresh_from_db()
        self.assertIsNone(self.user.anonymized_at)

    def test_exclusao_anonimiza_e_encerra_a_sessao(self):
        response = self.delete()
        self.assertRedirects(response, reverse('account_deleted'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, f'anonimizada-{self.user.pk}@anonimizado.invalid')
        self.assertEqual(self.user.first_name, '')
        self.assertEqual(self.user.last_name, '')
        self.assertFalse(self.user.has_usable_password())
        self.assertFalse(self.user.is_active)
        self.assertIsNotNone(self.user.anonymized_at)
        # Saiu da conta neste navegador.
        self.assertNotIn(SESSION_KEY, self.client.session)
        # O aceite fica, como prova (sem dado pessoal).
        self.assertEqual(Consent.objects.filter(user=self.user).count(), 1)

    def test_outras_sessoes_abertas_tambem_caem(self):
        other_device = Client()
        other_device.force_login(self.user)
        self.delete()
        # No "outro aparelho", a sessão não vale mais: a página pede login.
        response = other_device.get(reverse('account'))
        self.assertEqual(response.status_code, 302)

    def test_login_antigo_nao_funciona_mais(self):
        self.delete()
        response = Client().post(
            reverse('login'), {'username': 'cliente@example.com', 'password': GOOD_PASSWORD}
        )
        self.assertNotIn(SESSION_KEY, response.client.session)

    def test_apaga_registros_de_login_e_limpa_o_historico_do_admin(self):
        AccessAttempt.objects.create(
            username='cliente@example.com', ip_address='127.0.0.1', user_agent='x',
            http_accept='x', path_info='/conta/entrar/', get_data='', post_data='',
            failures_since_start=1,
        )
        LogEntry.objects.create(
            user=make_customer(email='dona@example.com', is_staff=True),
            content_type=ContentType.objects.get_for_model(User),
            object_id=str(self.user.pk), object_repr='cliente@example.com',
            action_flag=CHANGE,
        )
        self.delete()
        self.assertFalse(AccessAttempt.objects.filter(username='cliente@example.com').exists())
        self.assertFalse(LogEntry.objects.filter(object_repr='cliente@example.com').exists())

    def test_conta_do_admin_nao_se_exclui_pelo_site(self):
        staff = make_customer(email='dona@example.com', is_staff=True)
        self.client.force_login(staff)
        response = self.client.post(reverse('account_delete'), {'password': GOOD_PASSWORD, 'confirm': 'on'})
        self.assertRedirects(response, reverse('account'))
        staff.refresh_from_db()
        self.assertIsNone(staff.anonymized_at)
        self.assertTrue(staff.is_active)


class CleanupCommandTest(TestCase):
    """Comando limpar_dados_antigos: prazos de retenção (decisão 79)."""

    def setUp(self):
        self.now = timezone.now()

    def make_order(self, days_ago):
        """Cria um pedido e "volta no tempo" a data de criação."""
        order = Order.objects.create(
            customer_name='Clara Lima', phone='11999998888', cep='01001000',
            street='Rua das Flores', number='10', complement='ap 1',
            neighborhood='Centro', city='São Paulo', state='SP',
        )
        # created_at é auto_now_add: só update() consegue mudar a data.
        Order.objects.filter(pk=order.pk).update(created_at=self.now - timedelta(days=days_ago))
        return order

    def run_command(self, *args):
        """Roda o comando e devolve o que ele escreveu no terminal."""
        out = io.StringIO()
        call_command('limpar_dados_antigos', *args, stdout=out)
        return out.getvalue()

    def test_pedido_antigo_e_anonimizado_e_o_recente_nao(self):
        old = self.make_order(days_ago=ORDER_RETENTION.days + 1)
        recent = self.make_order(days_ago=10)
        self.run_command()
        old.refresh_from_db()
        recent.refresh_from_db()
        self.assertEqual(old.customer_name, 'Anonimizado')
        self.assertEqual(old.phone, '')
        self.assertEqual(old.cep, '')
        # Cidade e UF ficam (não identificam a cliente).
        self.assertEqual(old.city, 'São Paulo')
        self.assertEqual(recent.customer_name, 'Clara Lima')

    def test_conta_nunca_verificada_e_antiga_e_apagada(self):
        old = make_customer(email='velha@example.com', verified=False)
        recent = make_customer(email='nova@example.com', verified=False)
        verified = make_customer(email='verificada@example.com', verified=True)
        User.objects.filter(pk__in=[old.pk, verified.pk]).update(
            date_joined=self.now - timedelta(days=31)
        )
        self.run_command()
        self.assertFalse(User.objects.filter(pk=old.pk).exists())
        self.assertTrue(User.objects.filter(pk=recent.pk).exists())
        self.assertTrue(User.objects.filter(pk=verified.pk).exists())

    def test_tentativas_de_login_antigas_sao_apagadas(self):
        attempt = AccessAttempt.objects.create(
            username='x@example.com', ip_address='127.0.0.1', user_agent='x',
            http_accept='x', path_info='/conta/entrar/', get_data='', post_data='',
            failures_since_start=1,
        )
        AccessAttempt.objects.filter(pk=attempt.pk).update(attempt_time=self.now - timedelta(days=31))
        AccessLog.objects.create(username='x@example.com', ip_address='127.0.0.1', user_agent='x',
                                 http_accept='x', path_info='/conta/entrar/')
        self.run_command()
        self.assertFalse(AccessAttempt.objects.exists())
        self.assertFalse(AccessLog.objects.exists())

    def test_dry_run_nao_altera_nada_e_a_saida_nao_tem_dado_pessoal(self):
        order = self.make_order(days_ago=ORDER_RETENTION.days + 1)
        output = self.run_command('--dry-run')
        order.refresh_from_db()
        self.assertEqual(order.customer_name, 'Clara Lima')
        self.assertIn('seriam anonimizados: 1', output)
        self.assertNotIn('Clara', output)


class LegalPagesTest(TestCase):
    """Política, Termos, aviso de cookies e identificação do fornecedor."""

    def test_politica_e_termos_sao_rascunhos_com_versao(self):
        for name, version in [('privacy', PRIVACY_POLICY_VERSION), ('terms', TERMS_VERSION)]:
            with self.subTest(pagina=name):
                response = self.client.get(reverse(name))
                self.assertContains(response, 'RASCUNHO')
                self.assertContains(response, f'Versão {version}')

    def test_politica_lista_operadores_com_hospedagem_provisoria(self):
        response = self.client.get(reverse('privacy'))
        self.assertContains(response, 'Mercado Pago')
        self.assertContains(response, 'PROVISÓRIO: empresa ainda não definida')
        self.assertContains(response, 'elegancia.crist@gmail.com')

    @override_settings(STORE_LEGAL_NAME='', STORE_CNPJ='', STORE_ADDRESS='')
    def test_sem_cnpj_mostra_a_definir(self):
        response = self.client.get(reverse('terms'))
        self.assertContains(response, 'CNPJ: [A DEFINIR PELA DONA]')

    @override_settings(STORE_LEGAL_NAME='Loja Exemplo', STORE_CNPJ='00.000.000/0001-00',
                       STORE_ADDRESS='Rua Exemplo, 1')
    def test_com_cnpj_preenchido_aparece_sem_mexer_em_template(self):
        response = self.client.get(reverse('home'))
        # No rodapé de todas as páginas.
        self.assertContains(response, 'CNPJ 00.000.000/0001-00')

    def test_aviso_de_cookies_comeca_escondido(self):
        # O JavaScript mostra o aviso; sem JS ele fica escondido (hidden).
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'id="aviso-cookies" role="region" aria-label="Aviso de cookies" hidden')

    def test_site_nao_cria_cookie_alem_dos_necessarios(self):
        # Visitar páginas comuns não cria cookie nenhum além de sessão/CSRF.
        response = self.client.get(reverse('home'))
        self.assertTrue(set(response.cookies.keys()) <= {'sessionid', 'csrftoken', 'messages'})

    def test_login_nao_grava_historico_de_acessos(self):
        make_customer()
        self.client.post(reverse('login'), {'username': 'cliente@example.com', 'password': GOOD_PASSWORD})
        # AXES_DISABLE_ACCESS_LOG = True (decisão 83).
        self.assertFalse(AccessLog.objects.exists())


# ===========================================================================
# v2 Etapa 5 — pedidos ligados à conta
# ===========================================================================

class DeleteAccountWithOrdersTest(TestCase):
    """Exclusão bloqueada enquanto houver pedido ativo (decisão 92)."""

    def setUp(self):
        self.user = make_customer()
        self.variant = make_variant(stock=10)
        self.client.force_login(self.user)

    def delete(self):
        return self.client.post(reverse('account_delete'), {'password': GOOD_PASSWORD, 'confirm': 'on'})

    def test_pedido_ativo_bloqueia_get_e_post(self):
        order = make_order(user=self.user, variant=self.variant)
        page = self.client.get(reverse('account_delete'))
        self.assertContains(page, f'um pedido em andamento (nº {order.pk})')
        self.assertNotContains(page, 'name="password"')  # o formulário nem aparece
        # POST direto (sem passar pela página) também não exclui.
        self.delete()
        self.user.refresh_from_db()
        self.assertIsNone(self.user.anonymized_at)

    def test_pedido_pago_e_enviado_recente_tambem_bloqueiam(self):
        for status in (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED):
            with self.subTest(status=status):
                order = make_order(user=self.user, status=status, variant=self.variant)
                # Entregue há pouco: o prazo de 30 dias conta da ENTREGA (decisão 95).
                Order.objects.filter(pk=order.pk).update(
                    shipped_at=timezone.now(), delivered_at=timezone.now()
                )
                self.delete()
                self.user.refresh_from_db()
                self.assertIsNone(self.user.anonymized_at)
                Order.objects.filter(pk=order.pk).update(status=Order.Status.EXPIRED)

    def test_enviado_nao_entregue_bloqueia_mesmo_depois_de_30_dias(self):
        order = make_order(user=self.user, status=Order.Status.SHIPPED, variant=self.variant)
        Order.objects.filter(pk=order.pk).update(shipped_at=timezone.now() - timedelta(days=60))
        self.delete()
        self.user.refresh_from_db()
        self.assertIsNone(self.user.anonymized_at)

    def test_pedidos_encerrados_nao_bloqueiam_e_ficam_guardados(self):
        expired = make_order(user=self.user, status=Order.Status.EXPIRED, variant=self.variant)
        shipped = make_order(user=self.user, status=Order.Status.DELIVERED, variant=self.variant)
        # Enviado há 65 dias, entregue há 60: vale a data da entrega.
        Order.objects.filter(pk=shipped.pk).update(
            shipped_at=timezone.now() - timedelta(days=65),
            delivered_at=timezone.now() - timedelta(days=60),
        )
        response = self.delete()
        self.assertRedirects(response, reverse('account_deleted'))
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.anonymized_at)
        # Os pedidos continuam ligados à conta (anonimizada), pelo prazo legal.
        self.assertEqual(set(self.user.orders.all()), {expired, shipped})


class ExportOrdersTest(TestCase):
    """A exportação JSON inclui os pedidos da conta (decisão 93)."""

    def setUp(self):
        self.user = make_customer()
        variant = make_variant(price='150.00', stock=10)
        self.order = make_order(user=self.user, variant=variant, quantity=2, shipping_cost='19.90')
        other = make_customer(email='outra@example.com')
        make_order(user=other, variant=variant, customer_name='Ana Souza')
        self.client.force_login(self.user)

    def test_exporta_os_proprios_pedidos_e_nunca_os_de_outra_conta(self):
        response = self.client.post(reverse('account_export'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(data['pedidos']), 1)
        exported = data['pedidos'][0]
        self.assertEqual(exported['numero'], self.order.pk)
        self.assertEqual(exported['status'], 'Aguardando pagamento')
        self.assertEqual(exported['itens'][0]['quantidade'], 2)
        # Dinheiro como texto, sem perder centavos.
        self.assertEqual(exported['frete'], '19.90')
        self.assertEqual(exported['total'], '319.90')
        self.assertEqual(exported['entrega']['rua'], 'Rua das Flores')
        self.assertNotIn('Ana Souza', response.content.decode('utf-8'))


class AnonymizeAdminActionTest(TestCase):
    """Ação "Anonimizar contas" no admin (decisão 94)."""

    def setUp(self):
        self.owner = User.objects.create_superuser(email='dona@example.com', password=GOOD_PASSWORD)
        login_admin(self.client, self.owner)
        self.customer = make_customer(email='clara@example.com', first_name='Clara')
        self.url = reverse('admin:contas_user_changelist')

    def run_action(self, *users, confirm=False):
        data = {'action': 'anonymize_accounts', '_selected_action': [user.pk for user in users]}
        if confirm:
            data['confirm'] = 'yes'
        return self.client.post(self.url, data, follow=True)

    def test_primeiro_passo_so_mostra_a_confirmacao(self):
        response = self.run_action(self.customer)
        self.assertContains(response, 'Não dá para desfazer')
        self.assertContains(response, 'clara@example.com')
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.anonymized_at)

    def test_confirmando_anonimiza(self):
        response = self.run_action(self.customer, confirm=True)
        self.assertContains(response, '1 conta(s) anonimizada(s)')
        self.customer.refresh_from_db()
        self.assertIsNotNone(self.customer.anonymized_at)
        self.assertEqual(self.customer.first_name, '')

    def test_pula_equipe_e_conta_com_pedido_ativo(self):
        staff = make_customer(email='equipe@example.com', is_staff=True)
        busy = make_customer(email='ocupada@example.com')
        make_order(user=busy, variant=make_variant())
        confirmation = self.run_action(staff, busy, self.owner)
        self.assertContains(confirmation, 'conta da equipe')
        self.assertContains(confirmation, 'tem pedido em andamento')
        self.assertContains(confirmation, 'Nenhuma das contas selecionadas pode ser anonimizada')
        self.run_action(staff, busy, self.owner, confirm=True)
        for user in (staff, busy, self.owner):
            user.refresh_from_db()
            self.assertIsNone(user.anonymized_at)

    def test_grupo_loja_nao_ve_a_acao(self):
        """Sem a permissão de editar contas, a ação não existe para a conta."""
        call_command('criar_grupos', stdout=io.StringIO())
        staff = make_customer(email='equipe@example.com', is_staff=True)
        staff.groups.add(Group.objects.get(name='Loja'))
        client = Client()
        login_admin(client, staff)
        self.assertEqual(client.post(self.url, {
            'action': 'anonymize_accounts', '_selected_action': [self.customer.pk], 'confirm': 'yes',
        }).status_code, 403)
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.anonymized_at)


class CleanupKeepsAccountsWithOrdersTest(TestCase):
    """Conta nunca verificada COM pedido não é apagada pelo comando de limpeza."""

    def test_conta_com_pedido_fica(self):
        user = make_customer(email='antiga@example.com', verified=False)
        make_order(user=user, variant=make_variant())
        User.objects.filter(pk=user.pk).update(date_joined=timezone.now() - timedelta(days=31))
        call_command('limpar_dados_antigos', stdout=io.StringIO())
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
