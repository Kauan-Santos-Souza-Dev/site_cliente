"""Configuração do app de admin que troca o site padrão pelo site com 2FA.

Por que um arquivo separado (e não contas/apps.py)?
O Django escolhe sozinho a configuração de um app olhando as classes
AppConfig do arquivo apps.py. Se houvesse duas lá (a do app contas e esta),
ele não saberia qual usar. Aqui ela fica isolada e é citada pelo caminho
completo no INSTALLED_APPS.
"""

from django.contrib.admin.apps import AdminConfig


class LojaAdminConfig(AdminConfig):
    """O mesmo django.contrib.admin, mas com o LojaAdminSite como `admin.site`.

    Com isso, todo `@admin.register(...)` do projeto registra os models no
    site com 2FA, sem mudar nada nos arquivos admin.py.
    """

    default_site = 'contas.admin_site.LojaAdminSite'
