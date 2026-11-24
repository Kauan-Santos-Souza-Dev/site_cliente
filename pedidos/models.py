"""Models de pedidos: Order (o pedido), OrderItem (cada peça) e ShippingRate (frete por UF)."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone

from loja.models import ProductVariant

# As 27 unidades federativas, para o campo "UF" do endereço.
STATE_CHOICES = [
    (uf, uf) for uf in [
        'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS',
        'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC',
        'SP', 'SE', 'TO',
    ]
]

# Por quanto tempo, depois da ENTREGA, o pedido ainda conta como "ativo"
# (decisões 92 e 95): o prazo de desistência do CDC (7 dias APÓS o recebimento)
# pode estar correndo. Os 30 dias dão folga. Pergunta à dona.
DELIVERED_ACTIVE_PERIOD = timedelta(days=30)


class Order(models.Model):
    """Pedido feito pelo site, sempre ligado à conta da cliente (v2 Etapa 5)."""

    class Status(models.TextChoices):
        """Situações do pedido. O 1º valor vai para o banco; o 2º aparece na tela."""

        AWAITING_PAYMENT = 'aguardando_pagamento', 'Aguardando pagamento'
        PAID = 'pago', 'Pago'
        EXPIRED = 'expirado', 'Expirado'
        CANCELLED = 'cancelado', 'Cancelado'
        SHIPPED = 'enviado', 'Enviado'
        DELIVERED = 'entregue', 'Entregue'
        REFUNDED = 'estornado', 'Estornado'

    # Tabela de transições permitidas (decisão 87): {status atual: {para onde pode ir}}.
    # Um status que não leva a lugar nenhum (conjunto vazio) é FINAL.
    # "Pago" só é alcançado pela confirmação do gateway (Etapas 7 e 8): nenhuma
    # tela do admin oferece essa opção.
    ALLOWED_TRANSITIONS = {
        Status.AWAITING_PAYMENT: {Status.PAID, Status.EXPIRED, Status.CANCELLED},
        Status.PAID: {Status.SHIPPED, Status.REFUNDED},
        Status.SHIPPED: {Status.DELIVERED, Status.REFUNDED},
        # Entregue ainda pode ser estornado: desistência do CDC art. 49.
        Status.DELIVERED: {Status.REFUNDED},
        Status.EXPIRED: set(),
        Status.CANCELLED: set(),
        Status.REFUNDED: set(),
    }

    # Transições que devolvem as peças ao estoque. Estorno de pedido ENVIADO ou
    # ENTREGUE não está aqui: a peça está com a cliente e só volta ao estoque
    # quando chegar e for conferida. A dona usa a ação "Devolver peças ao
    # estoque" do admin (restore_stock_manually, decisão 97).
    STOCK_RETURNING_TRANSITIONS = {
        (Status.AWAITING_PAYMENT, Status.EXPIRED),
        (Status.AWAITING_PAYMENT, Status.CANCELLED),
        (Status.PAID, Status.REFUNDED),
    }

    # Dona do pedido. PROTECT: o banco recusa apagar uma conta que tem pedido
    # (o caminho é anonimizar a conta, decisão 78). null=True SÓ para os
    # pedidos da v1, feitos sem conta (decisão 86); todo pedido novo tem dona.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='orders', verbose_name='conta',
    )

    # Dados de entrega: só o necessário para entregar (LGPD).
    customer_name = models.CharField('nome', max_length=120)
    phone = models.CharField('telefone/WhatsApp', max_length=11, help_text='Só dígitos, com DDD.')
    cep = models.CharField('CEP', max_length=8, help_text='Só dígitos.')
    street = models.CharField('rua', max_length=150)
    number = models.CharField('número', max_length=20)
    complement = models.CharField('complemento', max_length=100, blank=True)
    neighborhood = models.CharField('bairro', max_length=100)
    city = models.CharField('cidade', max_length=100)
    state = models.CharField('UF', max_length=2, choices=STATE_CHOICES)

    status = models.CharField(
        'status', max_length=20, choices=Status.choices, default=Status.AWAITING_PAYMENT
    )
    # Frete calculado no momento da compra (decisão 90). Fica gravado: se a
    # tabela de frete mudar depois, o pedido continua com o valor cobrado.
    # Vazio só nos pedidos da v1 ("frete a combinar").
    shipping_cost = models.DecimalField(
        'frete (R$)', max_digits=8, decimal_places=2, null=True, blank=True
    )
    # Até quando as peças ficam reservadas esperando o pagamento (decisão 88).
    # Vazio = nunca expira sozinho (pedidos da v1).
    expires_at = models.DateTimeField('reservado até', null=True, blank=True)
    # Quando virou "enviado" (usado para saber se o pedido ainda é "ativo").
    shipped_at = models.DateTimeField('enviado em', null=True, blank=True)
    # Quando virou "entregue": o bloqueio de exclusão de conta conta daqui (decisão 95).
    delivered_at = models.DateTimeField('entregue em', null=True, blank=True)
    # Quando as peças voltaram ao estoque (automático ou manual). Serve de
    # registro e de trava: o estoque nunca é devolvido duas vezes (decisão 97).
    stock_restored_at = models.DateTimeField('estoque devolvido em', null=True, blank=True)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'pedido'
        verbose_name_plural = 'pedidos'
        ordering = ['-created_at']
        # Índice: deixa rápida a busca "pedidos aguardando com prazo vencido",
        # feita a cada visita à página de produto e pelo comando expirar_pedidos.
        indexes = [models.Index(fields=['status', 'expires_at'], name='order_status_expires_idx')]

    def __str__(self):
        return f'Pedido nº {self.pk}'

    # --- Totais --------------------------------------------------------------

    @property
    def items_total(self):
        """Soma dos itens (sem frete)."""
        return sum((item.subtotal for item in self.items.all()), Decimal('0'))

    @property
    def total(self):
        """Itens + frete."""
        return self.items_total + (self.shipping_cost or Decimal('0'))

    # --- Regras de status ----------------------------------------------------

    def status_in_database(self, lock=False):
        """Status que está salvo no banco agora (None se o pedido é novo).

        lock=True usa select_for_update(): trava a linha do pedido até o fim da
        transação. Se duas requisições mudarem o status ao mesmo tempo (ex.: o
        comando de expiração e a confirmação do pagamento), a segunda ESPERA a
        primeira terminar e já enxerga o status novo. Assim o estoque nunca
        volta em dobro. Só funciona dentro de transaction.atomic().
        """
        if self.pk is None:
            return None
        orders = Order.objects.filter(pk=self.pk)
        if lock:
            orders = orders.select_for_update()
        return orders.values_list('status', flat=True).first()

    @classmethod
    def can_change(cls, old_status, new_status):
        """Diz se a transição old_status -> new_status é permitida.

        Ficar no mesmo status é sempre permitido (ex.: a dona corrige o
        endereço sem mexer no status).
        """
        if old_status == new_status:
            return True
        return new_status in cls.ALLOWED_TRANSITIONS.get(old_status, set())

    def check_transition(self, old_status):
        """Lança ValidationError se a mudança de status não é permitida."""
        if old_status is None:
            return  # pedido sendo criado agora
        if not self.can_change(old_status, self.status):
            old_label = self.Status(old_status).label
            new_label = self.Status(self.status).label
            raise ValidationError(
                {'status': f'Não é possível passar de "{old_label}" para "{new_label}".'}
            )

    def clean(self):
        """Validação usada pelos formulários (inclusive o admin)."""
        self.check_transition(self.status_in_database())

    def save(self, *args, **kwargs):
        """Salva o pedido aplicando a tabela de transições.

        A regra fica aqui (e não só no admin) para valer em qualquer caminho:
        admin, comando de expiração, shell e, nas Etapas 7 e 8, o webhook.
        transaction.atomic(): mudar o status e devolver o estoque acontecem
        juntos; se algo falhar no meio, nada é gravado.
        """
        with transaction.atomic():
            old_status = self.status_in_database(lock=True)
            self.check_transition(old_status)
            if old_status != self.Status.SHIPPED and self.status == self.Status.SHIPPED:
                self.shipped_at = timezone.now()
            if old_status != self.Status.DELIVERED and self.status == self.Status.DELIVERED:
                self.delivered_at = timezone.now()
            super().save(*args, **kwargs)
            if (old_status, self.status) in self.STOCK_RETURNING_TRANSITIONS:
                self.restore_stock()

    def restore_stock(self):
        """Devolve ao estoque as peças de cada item do pedido.

        F('stock') + quantidade: o próprio banco soma, em vez de o Python ler o
        valor, somar e gravar. Assim não perdemos uma alteração feita por outra
        pessoa ao mesmo tempo.

        order_by('variant_id'): todos os caminhos tocam as variações na MESMA
        ordem (menor id primeiro). Se dois processos devolvessem estoque em
        ordens opostas (A depois B / B depois A), cada um poderia ficar
        esperando a trava do outro para sempre: um "deadlock".
        """
        for item in self.items.order_by('variant_id'):
            if item.variant_id:  # a variação pode ter sido apagada (SET_NULL)
                ProductVariant.objects.filter(pk=item.variant_id).update(
                    stock=F('stock') + item.quantity
                )
        # update(): grava só este campo, sem passar de novo pelo save() (que
        # reaplicaria as regras de transição e a trava).
        self.stock_restored_at = timezone.now()
        Order.objects.filter(pk=self.pk).update(stock_restored_at=self.stock_restored_at)

    def restore_stock_manually(self):
        """Devolve o estoque de um pedido ESTORNADO que já tinha sido enviado.

        A dona usa isto depois de receber a peça de volta e conferir que está
        em bom estado (decisão 97). Devolve True se devolveu, False se o pedido
        não é elegível: precisa estar estornado, ter sido enviado e ainda não
        ter tido o estoque devolvido.

        select_for_update(): trava a linha do pedido. Se a dona clicar duas
        vezes (ou duas pessoas ao mesmo tempo), a segunda espera, relê
        stock_restored_at já preenchido e não devolve de novo.
        """
        with transaction.atomic():
            locked = Order.objects.select_for_update().get(pk=self.pk)
            if (
                locked.status != self.Status.REFUNDED
                or locked.shipped_at is None
                or locked.stock_restored_at is not None
            ):
                return False
            locked.restore_stock()
            self.stock_restored_at = locked.stock_restored_at
            return True

    # --- Exibição ------------------------------------------------------------

    @property
    def is_awaiting_payment(self):
        """Atalho para os templates."""
        return self.status == self.Status.AWAITING_PAYMENT


def active_orders(user, now=None):
    """Pedidos "ativos" da conta: ainda há algo a fazer com eles (decisão 92).

    - aguardando pagamento (peças reservadas, pagamento em curso);
    - pago (a loja ainda vai entregar);
    - enviado (a entrega está em curso, sem limite de tempo: a dona precisa
      marcar como entregue, decisão 95);
    - entregue há menos de DELIVERED_ACTIVE_PERIOD (desistência em curso).

    Q() junta condições com "ou" (|). Sem Q, o filter() só sabe fazer "e".
    """
    now = now or timezone.now()
    return user.orders.filter(
        Q(status__in=[Order.Status.AWAITING_PAYMENT, Order.Status.PAID])
        | Q(status=Order.Status.SHIPPED)
        | Q(status=Order.Status.DELIVERED, delivered_at__gt=now - DELIVERED_ACTIVE_PERIOD)
    )


class OrderItem(models.Model):
    """Uma peça do pedido, com os dados CONGELADOS no momento da compra.

    Nome, tamanho e preço são copiados do produto. Se a loja mudar o preço
    ou o nome depois, o pedido continua mostrando o que a cliente comprou.
    """

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items', verbose_name='pedido'
    )
    # SET_NULL: se a variação for apagada, o item continua no histórico.
    # O vínculo serve para devolver o estoque ao cancelar ou expirar.
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='order_items', verbose_name='variação',
    )
    product_name = models.CharField('produto', max_length=120)
    size = models.CharField('tamanho', max_length=2)
    unit_price = models.DecimalField('preço unitário (R$)', max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField('quantidade')

    class Meta:
        verbose_name = 'item do pedido'
        verbose_name_plural = 'itens do pedido'

    def __str__(self):
        return f'{self.product_name} ({self.size}) x{self.quantity}'

    @property
    def subtotal(self):
        """Preço unitário x quantidade."""
        return self.unit_price * self.quantity


class ShippingRate(models.Model):
    """Preço do frete para uma UF, editável no admin (decisão 90).

    UF sem linha nesta tabela = a loja ainda não entrega lá (o checkout recusa).
    """

    class Region(models.TextChoices):
        """Regiões do Brasil, só para filtrar e agrupar no admin."""

        NORTE = 'norte', 'Norte'
        NORDESTE = 'nordeste', 'Nordeste'
        CENTRO_OESTE = 'centro_oeste', 'Centro-Oeste'
        SUDESTE = 'sudeste', 'Sudeste'
        SUL = 'sul', 'Sul'

    state = models.CharField('UF', max_length=2, choices=STATE_CHOICES, unique=True)
    region = models.CharField('região', max_length=12, choices=Region.choices)
    price = models.DecimalField(
        'frete (R$)', max_digits=8, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
    )
    # Os valores iniciais são EXEMPLOS (decisão 54). A dona desmarca ao
    # confirmar o valor real; o admin mostra um aviso enquanto houver algum.
    is_provisional = models.BooleanField(
        'PROVISÓRIO', default=True,
        help_text='Valor de exemplo. Desmarque quando a dona confirmar o valor real.',
    )

    class Meta:
        verbose_name = 'frete por UF'
        verbose_name_plural = 'fretes por UF'
        ordering = ['region', 'state']

    def __str__(self):
        return f'{self.state}: R$ {self.price}'
