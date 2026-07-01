from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.expenses.models import Expense, ProtocolBudgetItem
from apps.patients.models import Patient, Visit
from apps.protocols.models import Protocol, Site, VisitType


class Command(BaseCommand):
    help = "Crea datos mínimos y usuarios para mostrar Proyecto Córdoba a un cliente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="DemoCliente123!",
            help="Password para los usuarios de demo.",
        )
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Resetea passwords de usuarios existentes de demo.",
        )

    def handle(self, *args, **options):
        password = options["password"]
        reset_passwords = options["reset_passwords"]
        User = get_user_model()

        groups = {
            name: Group.objects.get_or_create(name=name)[0]
            for name in ["site_admin", "coordinator", "assistant", "auditor"]
        }

        site, _ = Site.objects.get_or_create(
            code="CBA-DEMO",
            defaults={
                "name": "Centro Córdoba Demo",
                "city": "Córdoba",
                "country": "Argentina",
                "is_active": True,
            },
        )

        users = [
            ("recepcion", "assistant", False),
            ("asistente", "assistant", False),
            ("coordinador", "coordinator", False),
            ("admin", "site_admin", True),
        ]
        for username, group_name, is_staff in users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "site": site,
                    "site_name": site.name,
                    "is_staff": is_staff,
                    "is_superuser": username == "admin",
                },
            )
            user.site = site
            user.site_name = site.name
            user.is_staff = is_staff or user.is_superuser
            if username == "admin":
                user.is_superuser = True
            if created or reset_passwords:
                user.set_password(password)
            user.save()
            user.groups.add(groups[group_name])

        admin_user = User.objects.get(username="admin")

        protocol, _ = Protocol.objects.get_or_create(
            code="CORD-DEMO-001",
            defaults={
                "site": site,
                "name": "Estudio demo de viáticos",
                "sponsor": "Sponsor Demo",
                "phase": "III",
                "currency": "USD",
                "max_daily_transport": Decimal("30.00"),
                "max_daily_meals": Decimal("20.00"),
                "max_daily_accommodation": Decimal("80.00"),
                "created_by": admin_user,
            },
        )
        if protocol.site_id != site.id:
            protocol.site = site
            protocol.save(update_fields=["site"])

        visit_type, _ = VisitType.objects.get_or_create(
            protocol=protocol,
            code="V1",
            defaults={
                "name": "Visita 1",
                "order": 1,
                "window_before_days": 3,
                "window_after_days": 3,
            },
        )

        patient, _ = Patient.objects.get_or_create(
            protocol=protocol,
            patient_code="CBA-001",
            defaults={"initials": "CD", "created_by": admin_user},
        )

        visit_v1, _ = Visit.objects.get_or_create(
            patient=patient,
            visit_type=visit_type,
            defaults={
                "scheduled_date": date.today(),
                "actual_date": date.today(),
                "status": "completed",
                "created_by": admin_user,
            },
        )

        visit_type_v2, _ = VisitType.objects.get_or_create(
            protocol=protocol,
            code="V2",
            defaults={
                "name": "Visita 2",
                "order": 2,
                "window_before_days": 3,
                "window_after_days": 3,
            },
        )

        visit_v2, _ = Visit.objects.get_or_create(
            patient=patient,
            visit_type=visit_type_v2,
            defaults={
                "scheduled_date": date.today(),
                "actual_date": date.today(),
                "status": "completed",
                "created_by": admin_user,
            },
        )

        visit_type_v3, _ = VisitType.objects.get_or_create(
            protocol=protocol,
            code="V3",
            defaults={
                "name": "Visita 3",
                "order": 3,
                "window_before_days": 3,
                "window_after_days": 3,
            },
        )

        visit_v3, _ = Visit.objects.get_or_create(
            patient=patient,
            visit_type=visit_type_v3,
            defaults={
                "scheduled_date": date.today(),
                "actual_date": date.today(),
                "status": "completed",
                "created_by": admin_user,
            },
        )

        ProtocolBudgetItem.objects.get_or_create(
            protocol=protocol,
            visit_type=visit_type,
            category="transport",
            defaults={
                "amount_usd": Decimal("30.00"),
                "notes": "Tope demo para taxi/remis",
                "created_by": admin_user,
            },
        )

        Expense.objects.get_or_create(
            visit=visit_v1,
            category="transport",
            expense_date=date.today(),
            submitted_by=User.objects.get(username="asistente"),
            defaults={
                "amount": Decimal("25000.00"),
                "currency": "ARS",
                "exchange_rate_to_usd": Decimal("1000.0000"),
                "amount_usd": Decimal("25.00"),
                "description": "Taxi del paciente al site",
                "vendor": "Taxi Demo",
                "status": "pending_review",
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo de cliente lista."))
        self.stdout.write("Usuarios: admin, recepcion, asistente, coordinador")
        self.stdout.write(f"Password: {password}")
