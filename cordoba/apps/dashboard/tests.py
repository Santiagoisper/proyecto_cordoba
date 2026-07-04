"""
Tests del dashboard: tablero global de gastos y export CSV de visitas.
Corre con: cd cordoba && python manage.py test apps.dashboard
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.protocols.models import Protocol, Site, VisitType
from apps.patients.models import Patient, Visit
from apps.expenses.models import Expense, ExpensePeriod

User = get_user_model()


class BaseDashboardTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        for name in ('coordinator', 'assistant', 'auditor'):
            Group.objects.get_or_create(name=name)

        cls.site = Site.objects.create(code='SITE-DB', name='Centro Dashboard')
        cls.other_site = Site.objects.create(code='SITE-OTRO', name='Otro Centro')

        cls.coordinator = User.objects.create_user(
            username='coord_db', password='testpass123', site=cls.site
        )
        cls.coordinator.groups.add(Group.objects.get(name='coordinator'))

        cls.assistant = User.objects.create_user(
            username='asst_db', password='testpass123', site=cls.site
        )
        cls.assistant.groups.add(Group.objects.get(name='assistant'))

        cls.superuser = User.objects.create_superuser(
            username='admin_db', password='testpass123'
        )

        cls.protocol = Protocol.objects.create(
            code='PROT-DB-01', name='Protocolo dashboard', site=cls.site,
            created_by=cls.coordinator,
        )
        cls.visit_type = VisitType.objects.create(
            protocol=cls.protocol, name='Screening', code='SCR', order=1,
        )
        cls.patient = Patient.objects.create(
            protocol=cls.protocol, patient_code='001-001', created_by=cls.coordinator,
        )
        cls.visit = Visit.objects.create(
            patient=cls.patient, visit_type=cls.visit_type,
            scheduled_date=date(2025, 2, 10), created_by=cls.coordinator,
        )

        # Protocolo de otro site: no debe aparecer para usuarios scoped
        cls.other_protocol = Protocol.objects.create(
            code='PROT-OTRO-01', name='Protocolo ajeno', site=cls.other_site,
            created_by=cls.coordinator,
        )
        other_vt = VisitType.objects.create(
            protocol=cls.other_protocol, name='Screening', code='SCR', order=1,
        )
        other_patient = Patient.objects.create(
            protocol=cls.other_protocol, patient_code='099-001',
            created_by=cls.coordinator,
        )
        other_visit = Visit.objects.create(
            patient=other_patient, visit_type=other_vt,
            scheduled_date=date(2025, 2, 10), created_by=cls.coordinator,
        )

        Expense.objects.create(
            visit=cls.visit, category='transport', amount=Decimal('1000.00'),
            expense_date=date(2025, 2, 10), status='approved',
            submitted_by=cls.assistant,
        )
        Expense.objects.create(
            visit=cls.visit, category='meals', amount=Decimal('500.00'),
            expense_date=date(2025, 2, 10), status='pending_review',
            submitted_by=cls.assistant,
        )
        Expense.objects.create(
            visit=other_visit, category='transport', amount=Decimal('7777.00'),
            expense_date=date(2025, 2, 10), status='approved',
            submitted_by=cls.assistant,
        )


class GlobalBoardTest(BaseDashboardTestCase):

    def test_requires_login(self):
        resp = self.client.get(reverse('dashboard:global_board'))
        self.assertEqual(resp.status_code, 302)

    def test_forbidden_for_assistant(self):
        self.client.force_login(self.assistant)
        resp = self.client.get(reverse('dashboard:global_board'))
        self.assertEqual(resp.status_code, 403)

    def test_superuser_sees_all_sites(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(reverse('dashboard:global_board'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'PROT-DB-01')
        self.assertContains(resp, 'PROT-OTRO-01')
        self.assertContains(resp, 'Tablero global')

    def test_coordinator_scoped_to_own_site(self):
        self.client.force_login(self.coordinator)
        resp = self.client.get(reverse('dashboard:global_board'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'PROT-DB-01')
        self.assertNotContains(resp, 'PROT-OTRO-01')
        # El comprometido del site propio (1000) aparece; el ajeno (7777) no
        self.assertContains(resp, '1.000,00')
        self.assertNotContains(resp, '7.777,00')

    def test_pending_amount_not_in_committed(self):
        self.client.force_login(self.coordinator)
        resp = self.client.get(reverse('dashboard:global_board'))
        # 500 pendiente aparece en "En proceso" con 1 comprobante sin aprobar
        self.assertContains(resp, '500,00')
        self.assertContains(resp, 'sin aprobar')


class ExportVisitsCsvTest(BaseDashboardTestCase):

    def test_export_csv_returns_csv(self):
        self.client.force_login(self.coordinator)
        resp = self.client.get(reverse('dashboard:export_visits_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        content = resp.content.decode('utf-8-sig')
        self.assertIn('Protocolo', content)
        self.assertIn('001-001', content)

    def test_export_csv_forbidden_for_assistant(self):
        self.client.force_login(self.assistant)
        resp = self.client.get(reverse('dashboard:export_visits_csv'))
        self.assertEqual(resp.status_code, 403)
