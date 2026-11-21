"""Carrinho de compras guardado na sessão do Django.

O que é a sessão?
Quando alguém visita o site, o Django cria um cookie com um código aleatório
(sessionid). Os dados ficam no SERVIDOR (tabela django_session), ligados a
esse código. O navegador guarda só o código: a cliente não consegue mexer
nas quantidades editando o cookie. Assim temos um carrinho sem login.

O que guardamos na sessão:
    {"cart": {"12": 2, "15": 1}}   ->   {id da variação: quantidade}

As chaves são texto porque a sessão é salva como JSON, e no JSON as chaves
de um objeto são sempre texto. O PREÇO não fica na sessão: ele é lido do
banco toda vez, então o carrinho sempre mostra o preço atual. O preço
"congelado" da compra é guardado no pedido (OrderItem), na etapa 7.
"""

from decimal import Decimal

from loja.models import ProductVariant

# Nome da chave do carrinho dentro da sessão.
CART_SESSION_KEY = 'cart'


class Cart:
    """Lê e altera o carrinho que está na sessão da visitante."""

    def __init__(self, request):
        """Pega o carrinho da sessão ou começa um vazio."""
        self.session = request.session
        # get() só LÊ: quem nunca usou o carrinho não ganha sessão gravada no
        # banco nem cookie. A sessão só é salva quando o carrinho muda (save()).
        self.data = self.session.get(CART_SESSION_KEY, {})

    # --- Alterações ---------------------------------------------------------

    def add(self, variant, quantity):
        """Soma `quantity` peças da variação ao carrinho.

        Devolve uma mensagem de erro (texto) se não for possível,
        ou None se deu certo.
        """
        new_quantity = self.quantity_of(variant) + quantity
        error = self.check_stock(variant, new_quantity)
        if error:
            return error
        self.data[str(variant.id)] = new_quantity
        self.save()
        return None

    def update(self, variant, quantity):
        """Troca a quantidade da variação. Devolve erro (texto) ou None."""
        error = self.check_stock(variant, quantity)
        if error:
            return error
        self.data[str(variant.id)] = quantity
        self.save()
        return None

    def remove(self, variant):
        """Tira a variação do carrinho (se estiver lá)."""
        if str(variant.id) in self.data:
            del self.data[str(variant.id)]
            self.save()

    def clear(self):
        """Esvazia o carrinho (usado depois de criar o pedido)."""
        self.data.clear()
        self.save()

    def save(self):
        """Grava o carrinho na sessão.

        Atribuir session['cart'] = ... faz o Django perceber a mudança e
        salvar a sessão no fim da requisição. Se só alterássemos o dicionário
        por dentro, precisaríamos avisar com session.modified = True.
        """
        self.session[CART_SESSION_KEY] = self.data

    # --- Regras -------------------------------------------------------------

    @staticmethod
    def check_stock(variant, quantity):
        """Confere se dá para ter `quantity` peças desta variação no carrinho.

        Devolve a mensagem de erro, ou None se estiver tudo certo.
        """
        if not variant.product.is_active:
            return 'Este produto não está mais disponível.'
        if variant.stock == 0:
            return f'O tamanho {variant.size} está esgotado.'
        if quantity > variant.stock:
            peca = 'peça' if variant.stock == 1 else 'peças'
            return f'Temos apenas {variant.stock} {peca} no tamanho {variant.size}.'
        return None

    # --- Leitura ------------------------------------------------------------

    def quantity_of(self, variant):
        """Quantas peças desta variação já estão no carrinho."""
        return self.data.get(str(variant.id), 0)

    def count(self):
        """Total de peças no carrinho. Lê só a sessão, sem consultar o banco."""
        return sum(self.data.values())

    def items(self):
        """Itens do carrinho com os dados atuais do banco.

        Cada item é um dicionário com: variant, product, quantity, price,
        subtotal e stock_problem (True se o estoque baixou depois de a
        cliente adicionar; o checkout vai recusar até ela ajustar).
        """
        # Uma consulta só para todas as variações (e não uma por item).
        # select_related traz o produto junto; prefetch_related, as fotos.
        variants = (
            ProductVariant.objects.filter(id__in=self.data.keys())
            .select_related('product')
            .prefetch_related('product__images')
        )
        variants_by_id = {str(variant.id): variant for variant in variants}

        items = []
        for variant_id, quantity in list(self.data.items()):
            variant = variants_by_id.get(variant_id)
            # Variação apagada ou produto desativado: some do carrinho.
            if variant is None or not variant.product.is_active:
                del self.data[variant_id]
                self.save()
                continue
            items.append({
                'variant': variant,
                'product': variant.product,
                'quantity': quantity,
                'price': variant.product.price,
                'subtotal': variant.product.price * quantity,
                'stock_problem': quantity > variant.stock,
            })
        return items

    def total(self):
        """Soma dos subtotais. Decimal('0') para o resultado ser Decimal mesmo vazio."""
        return sum((item['subtotal'] for item in self.items()), Decimal('0'))
