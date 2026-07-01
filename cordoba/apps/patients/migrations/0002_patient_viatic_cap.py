# Generated migration for adding viatic_cap to Patient

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='patient',
            name='viatic_cap',
            field=models.DecimalField(
                decimal_places=2,
                default=10000,
                help_text='Tope máximo de viáticos que pagan los laboratorios para este paciente',
                max_digits=12
            ),
        ),
    ]
