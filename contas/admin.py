"""Admin de usuários, adaptado ao login por e-mail."""

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.template.response import TemplateResponse

from pedidos.models import active_orders

from .forms import AdminUserChangeForm, AdminUserCreateForm
from .models import Consent, User
from .privacy import anonymize_user


def anonymize_blocker(user):
    """Motivo pelo qual a conta NÃO pode ser anonimizada pelo admin, ou None.

    - Equipe (is_staff/is_superuser): anonimizar trancaria alguém fora do
      admin. Isso se resolve no servidor, por quem administra.
    - Já anonimizada: não há o que fazer.
    - Pedido ativo (decisão 92): a loja ainda precisa da conta para
      entregar, receber ou devolver.
    """
    if user.is_staff or user.is_superuser:
        return 'conta da equipe'
    if user.anonymized_at is not None:
        return 'já anonimizada'
    if active_orders(user).exists():
        return 'tem pedido em andamento'
    return None


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Reaproveita o admin de usuários do Django (troca de senha, permissões...).

    O original usa o campo "username", que não existe no nosso modelo. Por
    isso redefinimos os grupos de campos, a lista, a busca e a ordenação.
    """

    form = AdminUserChangeForm
    add_form = AdminUserCreateForm

    list_display = ('email', 'first_name', 'last_name', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups', 'anonymized_at')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Dados pessoais', {'fields': ('first_name', 'last_name')}),
        (
            'Permissões',
            {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')},
        ),
        ('Datas', {'fields': ('last_login', 'date_joined', 'anonymized_at')}),
    )
    # Data da exclusão pela cliente: só para consulta (decisão 78).
    readonly_fields = ('anonymized_at',)
    actions = ['anonymize_accounts']
    # Tela "Adicionar usuário".
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'usable_password', 'password1', 'password2'),
            },
        ),
    )


    # permissions=['change']: a ação só aparece para quem pode EDITAR contas
    # (a superusuária). O grupo "Loja" não tem essa permissão (decisão 76).
    @admin.action(description='Anonimizar contas selecionadas (exclusão LGPD)', permissions=['change'])
    def anonymize_accounts(self, request, queryset):
        """Anonimiza contas a pedido da cliente (decisão 94), com confirmação.

        Dois passos, como o "excluir selecionados" do próprio Django:
        1º POST (escolheu a ação): mostra a página de confirmação; nada muda.
        2º POST (clicou em "Sim, anonimizar"): o formulário reenvia as mesmas
           contas com confirm=yes, e só então anonimizamos.
        As regras são conferidas de novo no 2º passo: um pedido pode ter sido
        feito entre um clique e outro.
        """
        allowed = []
        skipped = []
        for user in queryset:
            reason = anonymize_blocker(user)
            if reason is None:
                allowed.append(user)
            else:
                skipped.append((user, reason))

        if request.POST.get('confirm') == 'yes':
            for user in allowed:
                anonymize_user(user)
            self.message_user(request, f'{len(allowed)} conta(s) anonimizada(s).', messages.SUCCESS)
            if skipped:
                self.message_user(
                    request, f'{len(skipped)} conta(s) pulada(s) (veja os motivos na confirmação).',
                    messages.WARNING,
                )
            return None  # None = volta para a lista de usuários

        context = {
            **self.admin_site.each_context(request),
            'title': 'Anonimizar contas',
            'opts': self.model._meta,
            'allowed': allowed,
            'skipped': skipped,
            'selected_ids': [user.pk for user in queryset],
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        }
        return TemplateResponse(request, 'admin/contas/anonymize_confirmation.html', context)


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    """Aceites da Política e dos Termos, SOMENTE LEITURA (decisão 77).

    O aceite é uma prova: ninguém pode criar, editar ou apagar pelo admin.
    Ele só nasce no cadastro do site.
    """

    list_display = ('user', 'privacy_policy_version', 'terms_version', 'accepted_at')
    list_filter = ('privacy_policy_version', 'terms_version')
    search_fields = ('user__email',)
    date_hierarchy = 'accepted_at'

    def has_add_permission(self, request):
        """Ninguém cria aceite pelo admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Ninguém edita aceite (a tela abre só para leitura)."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Ninguém apaga aceite pelo admin."""
        return False
