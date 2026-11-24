"""Regras de privacidade (LGPD): exportar, anonimizar e limpar dados antigos.

Por que um arquivo separado das views?
As mesmas regras são usadas por lugares diferentes: a página "Minha conta"
(exportar e excluir) e o comando `limpar_dados_antigos`. Deixar a regra
aqui, em funções pequenas, permite testá-la sozinha e não repetir código.

"Anonimizar" x "apagar":
- Apagar remove a linha do banco. Tudo que apontava para ela também some
  (ou fica sem dono).
- Anonimizar troca os dados pessoais por valores que não identificam
  ninguém, mas MANTÉM a linha. É o que a LGPD pede quando a loja precisa
  guardar o registro de uma venda pelo prazo legal (art. 16 I), mas não
  precisa mais saber de quem era (art. 12: dado anonimizado não é dado
  pessoal). Decisão 78.
"""

from axes.models import AccessAttempt, AccessFailureLog, AccessLog
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from pedidos.models import Order

from .legal import LOGIN_ATTEMPT_RETENTION, ORDER_RETENTION, UNVERIFIED_ACCOUNT_RETENTION
from .models import User

# Texto que substitui nomes e endereços anonimizados.
ANONYMIZED_TEXT = 'Anonimizado'


# ---------------------------------------------------------------------------
# Exportar (LGPD art. 18 II e V: acesso e portabilidade)
# ---------------------------------------------------------------------------

def export_user_data(user):
    """Monta um dicionário com os dados pessoais da conta, pronto para virar JSON.

    O hash da senha NÃO entra: não é útil para a cliente e, fora do banco,
    só serviria para alguém tentar adivinhar a senha.
    Pedidos: só os da própria conta (user.orders), decisão 93.
    """
    return {
        'loja': 'Elegância Cristã',
        'gerado_em': timezone.now().isoformat(),
        'conta': {
            'nome': user.first_name,
            'sobrenome': user.last_name,
            'email': user.email,
            'email_verificado': user.email_verified,
            'cadastrada_em': user.date_joined.isoformat(),
            'ultimo_login': user.last_login.isoformat() if user.last_login else None,
        },
        'aceites': [
            {
                'politica_de_privacidade': consent.privacy_policy_version,
                'termos_de_uso': consent.terms_version,
                'aceito_em': consent.accepted_at.isoformat(),
            }
            for consent in user.consents.all()
        ],
        'pedidos': [export_order(order) for order in user.orders.prefetch_related('items')],
    }


def money(value):
    """Decimal -> texto ("229.90"), ou None. Texto não perde centavos (decisão 33)."""
    return str(value) if value is not None else None


def export_order(order):
    """Um pedido em forma de dicionário, para a exportação."""
    return {
        'numero': order.pk,
        'feito_em': order.created_at.isoformat(),
        'status': order.get_status_display(),
        'itens': [
            {
                'produto': item.product_name,
                'tamanho': item.size,
                'quantidade': item.quantity,
                'preco_unitario': money(item.unit_price),
            }
            for item in order.items.all()
        ],
        'produtos': money(order.items_total),
        'frete': money(order.shipping_cost),
        'total': money(order.total),
        'entrega': {
            'nome': order.customer_name,
            'telefone': order.phone,
            'cep': order.cep,
            'rua': order.street,
            'numero': order.number,
            'complemento': order.complement,
            'bairro': order.neighborhood,
            'cidade': order.city,
            'uf': order.state,
        },
    }


# ---------------------------------------------------------------------------
# Excluir conta = anonimizar (LGPD art. 18 VI)
# ---------------------------------------------------------------------------

def anonymized_email(user):
    """E-mail que substitui o real. Único (leva o id) e impossível de receber.

    ".invalid" é um domínio reservado (RFC 2606): nunca existe na internet,
    então nenhum e-mail é enviado para ele por engano.
    """
    return f'anonimizada-{user.pk}@anonimizado.invalid'


def anonymize_user(user):
    """Apaga os dados pessoais da conta, mantendo a linha (decisão 78).

    Quem chama confere antes se a conta tem pedido ATIVO (decisão 92):
    a página "Excluir conta" e a ação "Anonimizar" do admin. Os pedidos
    continuam ligados à linha da conta, com os dados de entrega, pelo prazo
    da decisão 79.

    transaction.atomic(): ou tudo é anonimizado, ou nada muda. Uma conta
    "meio anonimizada" seria pior que as duas situações.
    """
    old_email = user.email
    with transaction.atomic():
        user.email = anonymized_email(user)
        user.first_name = ''
        user.last_name = ''
        # Senha "inutilizável": nenhuma senha confere. Como o hash mudou, o
        # Django também derruba TODAS as sessões abertas desta conta (ele
        # compara um resumo do hash a cada requisição).
        user.set_unusable_password()
        user.is_active = False
        user.email_verified = False
        user.last_login = None
        user.last_email_sent_at = None
        user.anonymized_at = timezone.now()
        user.save()

        delete_login_records(old_email)
        # Dispositivos de 2FA (só existem em contas do admin).
        TOTPDevice.objects.filter(user=user).delete()
        StaticDevice.objects.filter(user=user).delete()
        clean_admin_log(user)
        # Os aceites (Consent) ficam: depois da anonimização não identificam
        # ninguém e continuam provando o que foi aceito (decisão 77).


def delete_login_records(email):
    """Apaga os registros do django-axes (tentativas de login) deste e-mail."""
    AccessAttempt.objects.filter(username=email).delete()
    AccessLog.objects.filter(username=email).delete()
    AccessFailureLog.objects.filter(username=email).delete()


def clean_admin_log(user):
    """Tira o e-mail da conta do histórico do admin.

    O admin guarda um histórico de alterações (tabela django_admin_log), e
    cada linha leva o "nome" do objeto alterado; para uma conta, o e-mail.
    """
    content_type = ContentType.objects.get_for_model(User)
    LogEntry.objects.filter(content_type=content_type, object_id=str(user.pk)).update(
        object_repr='Conta anonimizada'
    )


# ---------------------------------------------------------------------------
# Limpeza periódica (decisão 79). Usadas pelo comando limpar_dados_antigos.
# Cada função recebe `now` (o "agora") para os testes poderem simular datas,
# e devolve quantos registros seriam/foram afetados.
# ---------------------------------------------------------------------------

def old_orders(now):
    """Pedidos com mais de 5 anos que ainda têm dados pessoais."""
    return Order.objects.filter(created_at__lt=now - ORDER_RETENTION).exclude(
        customer_name=ANONYMIZED_TEXT
    )


def anonymize_old_orders(now, dry_run=False):
    """Apaga nome, telefone e endereço dos pedidos antigos.

    Ficam a cidade, a UF, os itens e os valores: servem para a loja saber o
    que vendeu e para onde, sem identificar a cliente.
    update() muda tudo numa só instrução no banco e NÃO chama Order.save(),
    então nenhuma regra de status ou estoque é disparada.
    """
    orders = old_orders(now)
    count = orders.count()
    if not dry_run:
        orders.update(
            customer_name=ANONYMIZED_TEXT,
            phone='',
            cep='',
            street=ANONYMIZED_TEXT,
            number='',
            complement='',
            neighborhood='',
        )
    return count


def old_unverified_accounts(now):
    """Contas de cliente que nunca confirmaram o e-mail, criadas há mais de 30 dias."""
    return User.objects.filter(
        email_verified=False,
        is_staff=False,
        anonymized_at__isnull=True,
        date_joined__lt=now - UNVERIFIED_ACCOUNT_RETENTION,
        # Defesa extra: o checkout exige e-mail verificado, então essas contas
        # não deveriam ter pedido. Se tiverem, não são apagadas (e o PROTECT
        # do Order.user recusaria o delete de qualquer forma).
        orders__isnull=True,
    )


def delete_old_unverified_accounts(now, dry_run=False):
    """Apaga de verdade as contas nunca verificadas e antigas.

    Podem ser apagadas (em vez de anonimizadas) porque nunca fizeram
    pedido: o checkout exige e-mail verificado (decisão 72).
    """
    accounts = old_unverified_accounts(now)
    count = accounts.count()
    if not dry_run:
        for email in accounts.values_list('email', flat=True):
            delete_login_records(email)
        accounts.delete()
    return count


def delete_old_login_attempts(now, dry_run=False):
    """Apaga tentativas de login com mais de 30 dias e TODO o histórico de logins.

    O histórico de logins bem-sucedidos (AccessLog) deixou de ser gravado
    (AXES_DISABLE_ACCESS_LOG, decisão 83); aqui só some o que ficou de antes.
    """
    limit = now - LOGIN_ATTEMPT_RETENTION
    attempts = AccessAttempt.objects.filter(attempt_time__lt=limit)
    failures = AccessFailureLog.objects.filter(attempt_time__lt=limit)
    logs = AccessLog.objects.all()
    count = attempts.count() + failures.count() + logs.count()
    if not dry_run:
        attempts.delete()
        failures.delete()
        logs.delete()
    return count
