from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pagamentos', '0001_pagamento'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='qr_code_base64',
            field=models.TextField(blank=True, verbose_name='QR Code (Base64)'),
        ),
    ]
