"""Formulários do carrinho.

Os Forms do Django validam o que chega do navegador: tipo do dado (é um
número?), valor mínimo, se o tamanho escolhido existe... Nunca confiamos
no HTML: alguém pode enviar um POST "na mão" com qualquer valor.
A regra de estoque fica na classe Cart, que sabe o que já está no carrinho.
"""

from django import forms


class AddToCartForm(forms.Form):
    """Escolha de tamanho e quantidade na página do produto."""

    # O queryset real é definido no __init__, porque depende do produto.
    variant = forms.ModelChoiceField(
        queryset=None,
        label='Tamanho',
        error_messages={
            'required': 'Escolha um tamanho.',
            'invalid_choice': 'Este tamanho não está disponível.',
        },
    )
    quantity = forms.IntegerField(
        label='Quantidade',
        min_value=1,
        initial=1,
        error_messages={
            'required': 'Informe a quantidade.',
            'min_value': 'A quantidade mínima é 1.',
        },
    )

    def __init__(self, *args, product, **kwargs):
        """Só aceita tamanhos deste produto que ainda têm estoque."""
        super().__init__(*args, **kwargs)
        self.fields['variant'].queryset = product.variants.filter(stock__gt=0)


class UpdateQuantityForm(forms.Form):
    """Nova quantidade de um item, na página do carrinho."""

    quantity = forms.IntegerField(
        label='Quantidade',
        min_value=1,
        error_messages={
            'required': 'Informe a quantidade.',
            'min_value': 'A quantidade mínima é 1. Para tirar o item, use "Remover".',
        },
    )


def first_error(form):
    """Primeira mensagem de erro do formulário, para mostrar à cliente."""
    for errors in form.errors.values():
        return errors[0]
    return 'Não foi possível concluir. Tente novamente.'
