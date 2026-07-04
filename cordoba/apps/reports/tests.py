"""
Tests del módulo de reportes: PDF por visita y selects HTMX.
Corre con: cd cordoba && python manage.py test apps.reports
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.protocols.models import Protocol, Site, VisitType
from apps.patients.models import Patient, Visit
from apps.expenses.models import Expense, ExpensePeriod, AuditLog

User = get_user_model()


class BaseReportTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        Group.objects.get_or_create(name='coordinator')
        Group.objects.get_or_create(name='assistant')

        cls.coordinator = User.objects.create_user(
            username='coord_rep', password='testpass123'
        )
        cls.coordinator.groups.add(Group.objects.get(name='coordinator'))

        cls.assistant = User.objects.create_user(
            username='asst_rep', password='testpass123'
        )
        cls.assistant.groups.add(Group.objects.get(name='assistant'))

        cls.site = Site.objects.create(code='SITE-REP', name='Centro Reportes')
        cls.coordinator.site = cls.site
        cls.coordinator.save(update_fields=['site'])

        cls.protocol = Protocol.objects.create(
            code='PROT-REP-01',
            name='Protocolo reportes',
            site=cls.site,
            sponsor='Sponsor Test',
            created_by=cls.coordinator,
        )
        cls.visit_type = VisitType.objects.create(
            protocol=cls.protocol, name='Screening', code='SCR', order=1,
        )
        cls.other_visit_type = VisitType.objects.create(
            protocol=cls.protocol, name='Visita 2', code='V2', order=2,
        )
        cls.period = ExpensePeriod.objects.create(
            protocol=cls.protocol,
            name='Q1 2025',
            date_from=date(2025, 1, 1),
            date_to=date(2025, 3, 31),
            created_by=cls.coordinator,
        )
        cls.patient_a = Patient.objects.create(
            protocol=cls.protocol, patient_code='001-001', created_by=cls.coordinator,
        )
        cls.patient_b = Patient.objects.create(
            protocol=cls.protocol, patient_code='001-002', created_by=cls.coordinator,
        )

    def _approved_expense(self, patient, visit_type, amount, category='transport'):
        visit, _ = Visit.objects.get_or_create(
            patient=patient,
            visit_type=visit_type,
            defaults={'scheduled_date': date(2025, 2, 10), 'created_by': self.coordinator},
        )
        return Expense.objects.create(
            visit=visit,
            period=self.period,
            category=category,
            amount=Decimal(str(amount)),
            expense_date=date(2025, 2, 10),
            status='approved',
            submitted_by=self.assistant,
        )


class VisitPdfTest(BaseReportTestCase):

    def test_visit_pdf_requires_login(self):
        resp = self.client.post(reverse('reports:visit_pdf'))
        self.assertEqual(resp.status_code, 302)

    def test_visit_pdf_forbidden_for_assistant(self):
        self.client.force_login(self.assistant)
        resp = self.client.post(reverse('reports:visit_pdf'))
        self.assertEqual(resp.status_code, 403)

    def test_visit_pdf_returns_pdf_and_marks_exported(self):
        exp_a = self._approved_expense(self.patient_a, self.visit_type, '1500.00')
        exp_b = self._approved_expense(self.patient_b, self.visit_type, '2300.00', category='meals')
        # Gasto de otra visita: NO debe entrar al reporte ni marcarse exportado
        exp_other = self._approved_expense(self.patient_a, self.other_visit_type, '999.00')

        self.client.force_login(self.coordinator)
        resp = self.client.post(reverse('reports:visit_pdf'), {
            'protocol_id': self.protocol.pk,
            'visit_type_id': self.visit_type.pk,
            'period_id': self.period.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

        exp_a.refresh_from_db()
        exp_b.refresh_from_db()
        exp_other.refresh_from_db()
        self.assertEqual(exp_a.status, 'exported')
        self.assertEqual(exp_b.status, 'exported')
        self.assertEqual(exp_other.status, 'approved')

        self.assertTrue(AuditLog.objects.filter(
            action='exported', object_id=exp_a.pk, content_type='Expense',
        ).exists())

    def test_visit_pdf_error_when_no_expenses(self):
        self.client.force_login(self.coordinator)
        resp = self.client.post(reverse('reports:visit_pdf'), {
            'protocol_id': self.protocol.pk,
            'visit_type_id': self.visit_type.pk,
            'period_id': self.period.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/html', resp['Content-Type'])
        self.assertContains(resp, 'No hay gastos aprobados')

    def test_visit_pdf_rejects_visit_type_of_other_protocol(self):
        other_protocol = Protocol.objects.create(
            code='PROT-REP-02', name='Otro protocolo', site=self.site,
            created_by=self.coordinator,
        )
        foreign_vt = VisitType.objects.create(
            protocol=other_protocol, name='Screening', code='SCR', order=1,
        )
        self.client.force_login(self.coordinator)
        resp = self.client.post(reverse('reports:visit_pdf'), {
            'protocol_id': self.protocol.pk,
            'visit_type_id': foreign_vt.pk,
            'period_id': self.period.pk,
        })
        self.assertEqual(resp.status_code, 404)


class HtmxVisitTypesTest(BaseReportTestCase):

    def test_visit_types_for_protocol(self):
        self.client.force_login(self.coordinator)
        resp = self.client.get(
            reverse('reports:htmx_visit_types'), {'protocol': self.protocol.pk}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Screening')
        self.assertContains(resp, 'Visita 2')

    def test_visit_types_empty_without_protocol(self):
        self.client.force_login(self.coordinator)
        resp = self.client.get(reverse('reports:htmx_visit_types'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Primero seleccion')
