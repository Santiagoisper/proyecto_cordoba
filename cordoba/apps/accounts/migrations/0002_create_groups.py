"""
Migración de datos: crea los 4 grupos de roles del sistema.
No modificar — es la fuente de verdad para los roles GCP.
"""
from django.db import migrations


GROUPS = ['site_admin', 'coordinator', 'assistant', 'auditor']


def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for name in GROUPS:
        Group.objects.get_or_create(name=name)


def delete_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=GROUPS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_groups, delete_groups),
    ]
