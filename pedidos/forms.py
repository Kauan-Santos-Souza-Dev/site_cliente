"""Formulário de checkout: dados da cliente e endereço de entrega."""

import re

from django import forms

from .models import Order


def only_digits(text):
    """Remove tudo que não é número: "(11) 98533-5054" -> "11985335054"."""
    return re.sub(r'\D', '', text)


class CheckoutForm(forms.ModelForm):
    """ModelForm: os campos e as validações básicas vêm do model Order.

    Só listamos os campos que a CLIENTE preenche. Status e frete ficam de
    fora: ela não pode mandar, por exemplo, status="enviado" num POST.
    """

    # Telefone e CEP são declarados aqui (e não gerados pelo model) para
    # aceitar a digitação com parênteses, espaço e traço. No banco guardamos
    # só os dígitos: quem limpa são os métodos clean_phone e clean_cep.
    phone = forms.CharField(
        label='Telefone/WhatsApp (com DDD)',
        max_length=20,
        widget=forms.TextInput(attrs={
            'autocomplete': 'tel', 'inputmode': 'tel', 'placeholder': '(11) 91234-5678',
        }),
    )
    cep = forms.CharField(
        label='CEP',
        max_length=9,
        widget=forms.TextInput(attrs={
            'autocomplete': 'postal-code', 'inputmode': 'numeric', 'placeholder': '00000-000',
        }),
    )

    class Meta:
        model = Order
        fields = [
            'customer_name', 'phone',
            'cep', 'street', 'number', 'complement', 'neighborhood', 'city', 'state',
        ]
        labels = {'customer_name': 'Nome completo'}
        # autocomplete: o celular sugere nome, telefone e endereço já salvos.
        widgets = {
            'customer_name': forms.TextInput(attrs={'autocomplete': 'name'}),
            'street': forms.TextInput(attrs={'autocomplete': 'address-line1'}),
            'number': forms.TextInput(attrs={'inputmode': 'numeric'}),
            'complement': forms.TextInput(attrs={'autocomplete': 'address-line2'}),
            'neighborhood': forms.TextInput(attrs={'autocomplete': 'address-level3'}),
            'city': forms.TextInput(attrs={'autocomplete': 'address-level2'}),
            'state': forms.Select(attrs={'autocomplete': 'address-level1'}),
        }
    def __init__(self, *args, **kwargs):
        """Troca a 1ª opção da UF ("---------") por "Selecione"."""
        super().__init__(*args, **kwargs)
        self.fields['state'].choices = [('', 'Selecione')] + list(self.fields['state'].choices)[1:]

    def clean_phone(self):
        """Guarda só os dígitos e exige DDD + número (10 ou 11 dígitos)."""
        phone = only_digits(self.cleaned_data['phone'])
        if len(phone) not in (10, 11):
            raise forms.ValidationError('Informe o telefone com DDD, ex.: (11) 91234-5678.')
        return phone

    def clean_cep(self):
        """Guarda só os 8 dígitos do CEP."""
        cep = only_digits(self.cleaned_data['cep'])
        if len(cep) != 8:
            raise forms.ValidationError('O CEP deve ter 8 números, ex.: 01234-567.')
        return cep
