"""Admin de usuários, adaptado ao login por e-mail."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import AdminUserChangeForm, AdminUserCreateForm
from .models import Consent, User


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
