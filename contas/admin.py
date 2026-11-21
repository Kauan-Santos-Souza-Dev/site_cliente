"""Admin de usuários, adaptado ao login por e-mail."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import AdminUserChangeForm, AdminUserCreateForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Reaproveita o admin de usuários do Django (troca de senha, permissões...).

    O original usa o campo "username", que não existe no nosso modelo. Por
    isso redefinimos os grupos de campos, a lista, a busca e a ordenação.
    """

    form = AdminUserChangeForm
    add_form = AdminUserCreateForm

    list_display = ('email', 'first_name', 'last_name', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Dados pessoais', {'fields': ('first_name', 'last_name')}),
        (
            'Permissões',
            {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')},
        ),
        ('Datas', {'fields': ('last_login', 'date_joined')}),
    )
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
