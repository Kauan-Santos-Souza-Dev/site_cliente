"""Migration de dados: cria as 3 categorias fixas da loja.

Migration "normal" altera a estrutura do banco (tabelas e colunas). Esta é uma
migration de DADOS: usa RunPython para inserir linhas. Assim, qualquer pessoa
que rodar `migrate` já terá as categorias, sem cadastrar nada à mão.
"""

from django.db import migrations

# As categorias fixas do catálogo. A tupla é (nome, slug).
CATEGORIES = [
    ('Vestidos', 'vestidos'),
    ('Saias', 'saias'),
    ('Conjuntos', 'conjuntos'),
]


def create_categories(apps, schema_editor):
    # Em migrations usamos apps.get_model (e não import direto) para obter o
    # model como ele era NESTE ponto do histórico, mesmo que mude depois.
    Category = apps.get_model('loja', 'Category')
    for name, slug in CATEGORIES:
        # get_or_create evita duplicar se a migration rodar duas vezes.
        Category.objects.get_or_create(slug=slug, defaults={'name': name})


def remove_categories(apps, schema_editor):
    """Desfaz a migration (migrate loja 0001)."""
    Category = apps.get_model('loja', 'Category')
    Category.objects.filter(slug__in=[slug for _, slug in CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('loja', '0001_catalogo_inicial'),
    ]

    operations = [
        migrations.RunPython(create_categories, remove_categories),
    ]
