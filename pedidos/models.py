"""Models de pedidos: Order (o pedido) e OrderItem (cada peça do pedido)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F

from loja.models import ProductVariant

# As 27 unidades federativas, para o campo "UF" do endereço.
STATE_CHOICES = [
    (uf, uf) for uf in [
        'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS',
        'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC',
        'SP', 'SE', 'TO',
    ]
]


class Order(models.Model):
    """Pedido feito pelo site. O pagamento é combinado pelo WhatsApp."""

    class Status(models.TextChoices):
        """Situações do pedido. O 1º valor vai para o banco; o 2º aparece na tela."""

        NEW = 'novo', 'Novo'
        CONFIRMED = 'confirmado', 'Confirmado'
        SHIPPED = 'enviado', 'Enviado'
        CANCELLED = 'cancelado', 'Cancelado'

    # Dados da cliente: só o necessário para entregar (LGPD).
    customer_name = models.CharField('nome', max_length=120)
    phone = models.CharField('telefone/WhatsApp', max_length=11, help_text='Só dígitos, com DDD.')

    # Endereço de entrega.
    cep = models.CharField('CEP', max_length=8, help_text='Só dígitos.')
    street = models.CharField('rua', max_length=150)
    number = models.CharField('número', max_length=20)
    complement = models.CharField('complemento', max_length=100, blank=True)
    neighborhood = models.CharField('bairro', max_length=100)
    city = models.CharField('cidade', max_length=100)
    state = models.CharField('UF', max_length=2, choices=STATE_CHOICES)

    status = models.CharField(
        'status', max_length=10, choices=Status.choices, default=Status.NEW
    )
    # Frete: vazio na v1 ("a combinar"). Já existe para a v2 calcular sem refatorar.
    shipping_cost = models.DecimalField(
        'frete (R$)', max_digits=8, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'pedido'
        verbose_name_plural = 'pedidos'
        ordering = ['-created_at']

    def __str__(self):
        return f'Pedido nº {self.pk}'

    # --- Totais --------------------------------------------------------------

    @property
    def items_total(self):
        """Soma dos itens (sem frete)."""
        return sum((item.subtotal for item in self.items.all()), Decimal('0'))

    @property
    def total(self):
        """Itens + frete (quando a loja informar o frete)."""
        return self.items_total + (self.shipping_cost or Decimal('0'))

    # --- Regras de status ----------------------------------------------------

    def status_in_database(self, lock=False):
        """Status que está salvo no banco agora (None se o pedido é novo).

        lock=True usa select_for_update(): trava a linha do pedido até o fim da
        transação. Se duas pessoas cancelarem ao mesmo tempo, a segunda espera
        a primeira terminar e já enxerga "cancelado" (o estoque não volta em
        dobro). Só funciona dentro de transaction.atomic().
        """
        if self.pk is None:
            return None
        orders = Order.objects.filter(pk=self.pk)
        if lock:
            orders = orders.select_for_update()
        return orders.values_list('status', flat=True).first()

    def check_not_reopening(self, old_status):
        """Cancelado é final: não pode voltar para outro status."""
        if old_status == self.Status.CANCELLED and self.status != self.Status.CANCELLED:
            raise ValidationError(
                {'status': 'Pedido cancelado não pode ser reaberto. Faça um pedido novo.'}
            )

    def clean(self):
        """Validação usada pelos formulários (inclusive o admin)."""
        self.check_not_reopening(self.status_in_database())

    def save(self, *args, **kwargs):
        """Salva o pedido. Se ele ACABOU de ser cancelado, devolve o estoque.

        A regra fica aqui (e não só no admin) para valer em qualquer caminho:
        página do pedido no admin, listagem editável, ação em massa ou shell.
        transaction.atomic(): mudar o status e devolver o estoque acontecem
        juntos; se algo falhar no meio, nada é gravado.
        """
        with transaction.atomic():
            old_status = self.status_in_database(lock=True)
            self.check_not_reopening(old_status)
            being_cancelled = (
                old_status is not None
                and old_status != self.Status.CANCELLED
                and self.status == self.Status.CANCELLED
            )
            super().save(*args, **kwargs)
            if being_cancelled:
                self.restore_stock()

    def restore_stock(self):
        """Devolve ao estoque as peças de cada item do pedido.

        F('stock') + quantidade: o próprio banco soma, em vez de o Python ler o
        valor, somar e gravar. Assim não perdemos uma alteração feita por outra
        pessoa ao mesmo tempo.
        """
        for item in self.items.all():
            if item.variant_id:  # a variação pode ter sido apagada (SET_NULL)
                ProductVariant.objects.filter(pk=item.variant_id).update(
                    stock=F('stock') + item.quantity
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
    # O vínculo serve para devolver o estoque ao cancelar.
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
