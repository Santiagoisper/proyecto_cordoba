"""
E2E golden path — recorre el flujo clínico-administrativo completo en una sola
transacción de test con django.test.Client (HTMX, sin Playwright).

Ejecutar:
    cd cordoba
    $env:DJANGO_SETTINGS_MODULE = "config.settings.test"
    python manage.py test apps.expenses.tests_e2e_full -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.patients.models import Patient
from apps.protocols.models import Protocol, Site, VisitType

from .models import AuditLog, Expense, ExpensePeriod, ProtocolBudgetItem, ReceptionTicket
from .tasks import process_ocr_for_ticket
from .tests import BaseExpenseTestCase

User = get_user_model()


class FullProgramE2ETest(BaseExpenseTestCase):
    """Golden path E2E: recepción → OCR → revisión → aprobación → reportes → cierre."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        Group.objects.get_or_create(name='site_admin')
        Group.objects.get_or_create(name='auditor')

        cls.reception = User.objects.create_user(
            username='recep_e2e', password='testpass123'
        )
        cls.reception.groups.add(Group.objects.get(name='assistant'))
        cls.reception.site = cls.site
        cls.reception.save(update_fields=['site'])

        cls.auditor = User.objects.create_user(
            username='audit_e2e', password='testpass123'
        )
        cls.auditor.groups.add(Group.objects.get(name='auditor'))
        cls.auditor.site = cls.site
        cls.auditor.save(update_fields=['site'])

        cls.admin = User.objects.create_user(
            username='admin_e2e', password='testpass123', is_staff=True
        )
        cls.admin.groups.add(Group.objects.get(name='site_admin'))
        cls.admin.site = cls.site
        cls.admin.save(update_fields=['site'])

        ProtocolBudgetItem.objects.create(
            protocol=cls.protocol,
            visit_type=cls.visit_type,
            category='transport',
            amount_usd=Decimal('40.00'),
            created_by=cls.coordinator,
        )

        cls.visit_type_v2 = VisitType.objects.create(
            protocol=cls.protocol,
            name='Visita 2',
            code='V2',
            order=2,
            window_before_days=3,
            window_after_days=3,
        )
        cls.visit_type_v3 = VisitType.objects.create(
            protocol=cls.protocol,
            name='Visita 3',
            code='V3',
            order=3,
            window_before_days=3,
            window_after_days=3,
        )

        cls.site_b = Site.objects.create(code='SITE-E2E-B', name='Centro B E2E')
        cls.coord_b = User.objects.create_user(username='coord_b_e2e', password='testpass123')
        cls.coord_b.groups.add(Group.objects.get(name='coordinator'))
        cls.coord_b.site = cls.site_b
        cls.coord_b.save(update_fields=['site'])

        cls.protocol_b = Protocol.objects.create(
            code='PROT-E2E-B',
            name='Protocolo site B',
            site=cls.site_b,
            max_daily_meals=Decimal('2000.00'),
            max_daily_transport=Decimal('3000.00'),
            max_daily_accommodation=Decimal('10000.00'),
            created_by=cls.coord_b,
        )
        cls.patient_b = Patient.objects.create(
            protocol=cls.protocol_b,
            patient_code='B-E2E-001',
            created_by=cls.coord_b,
        )
        cls.period_b = ExpensePeriod.objects.create(
            protocol=cls.protocol_b,
            name='Q1 B',
            date_from=date(2025, 1, 1),
            date_to=date(2025, 3, 31),
            created_by=cls.coord_b,
        )

    def setUp(self):
        self.client = Client()
        self.period.status = 'open'
        self.period.closed_by = None
        self.period.closed_at = None
        self.period.save(update_fields=['status', 'closed_by', 'closed_at'])

    def _fake_ticket(self, name='ticket.jpg'):
        return SimpleUploadedFile(
            name,
            b'\xff\xd8\xff\xe0' + b'\x00' * 20,
            content_type='image/jpeg',
        )

    def _review_payload(self, amount='1500.00'):
        return {
            'category': 'transport',
            'amount': amount,
            'currency': 'ARS',
            'exchange_rate_to_usd': '1000.00',
            'expense_date': '2025-03-15',
            'vendor': 'Taxi Demo E2E',
            'description': 'Viaje al site',
        }

    def _upload_and_assign(self, visit_type, notes='Ticket E2E'):
        """Recepción sube ticket; asistente lo imputa y dispara OCR eager."""
        self.client.force_login(self.reception)
        resp = self.client.post(reverse('expenses:reception_upload'), {
            'file': self._fake_ticket(f'{visit_type.code}.jpg'),
            'notes': notes,
        })
        self.assertEqual(resp.status_code, 302)
        ticket = ReceptionTicket.objects.filter(status='pending_assignment').latest('pk')
        self.assertEqual(ticket.status, 'pending_assignment')

        self.client.force_login(self.assistant)
        resp = self.client.post(
            reverse('expenses:reception_assign', kwargs={'pk': ticket.pk}),
            {
                'protocol': self.protocol.pk,
                'patient': self.patient.pk,
                'visit_type_id': visit_type.pk,
                'category': 'transport',
                'expense_date': '2025-03-15',
                'description': f'Imputación {visit_type.code}',
            },
        )
        self.assertEqual(resp.status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'assigned')
        expense = ticket.assigned_expense
        self.assertIsNotNone(expense)
        self.assertTrue(expense.ticket_files.exists())
        return expense

    def _run_ocr(self, expense):
        ticket_file = expense.ticket_files.first()
        process_ocr_for_ticket(ticket_file.pk)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'pending_review')
        self.assertTrue(
            AuditLog.objects.filter(
                action='ocr_completed',
                content_type='Expense',
                object_id=expense.pk,
            ).exists()
        )

    def _assistant_review(self, expense):
        self.client.force_login(self.assistant)
        resp = self.client.post(
            reverse('expenses:review', kwargs={'pk': expense.pk}),
            self._review_payload(),
        )
        self.assertEqual(resp.status_code, 302)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'pending_review')
        self.assertEqual(expense.amount, Decimal('1500.00'))

    def _link_period(self, *expenses):
        for expense in expenses:
            expense.period = self.period
            expense.save(update_fields=['period'])

    def test_full_program_golden_path(self):
        """Flujo continuo: recepción, OCR, ramas observe/reject, reportes y cierre."""

        # ── 1. Gasto principal (V1): recepción → imputación → OCR → revisión ──
        expense_main = self._upload_and_assign(self.visit_type)
        self._run_ocr(expense_main)
        self._assistant_review(expense_main)

        # ── 2. Rama observe/correct (V2) ──
        expense_obs = self._upload_and_assign(self.visit_type_v2, notes='Rama observe')
        self._run_ocr(expense_obs)
        self._assistant_review(expense_obs)

        self.client.force_login(self.coordinator)
        resp = self.client.post(
            reverse('expenses:observe', kwargs={'pk': expense_obs.pk}),
            {'notes': 'Falta detalle del comercio'},
        )
        self.assertEqual(resp.status_code, 200)
        expense_obs.refresh_from_db()
        self.assertEqual(expense_obs.status, 'observed')

        self.client.force_login(self.assistant)
        resp = self.client.post(
            reverse('expenses:correct', kwargs={'pk': expense_obs.pk}),
            self._review_payload(amount='1800.00'),
        )
        self.assertEqual(resp.status_code, 302)
        expense_obs.refresh_from_db()
        self.assertEqual(expense_obs.status, 'pending_review')

        self.client.force_login(self.coordinator)
        resp = self.client.post(reverse('expenses:approve', kwargs={'pk': expense_obs.pk}))
        self.assertEqual(resp.status_code, 200)
        expense_obs.refresh_from_db()
        self.assertEqual(expense_obs.status, 'approved')

        # ── 3. Rama reject (V3) ──
        expense_rej = self._upload_and_assign(self.visit_type_v3, notes='Rama reject')
        self._run_ocr(expense_rej)
        self._assistant_review(expense_rej)

        self.client.force_login(self.coordinator)
        resp = self.client.post(
            reverse('expenses:reject', kwargs={'pk': expense_rej.pk}),
            {'notes': 'Comprobante ilegible'},
        )
        self.assertEqual(resp.status_code, 200)
        expense_rej.refresh_from_db()
        self.assertEqual(expense_rej.status, 'rejected')
        self.assertTrue(
            AuditLog.objects.filter(action='rejected', object_id=expense_rej.pk).exists()
        )

        # ── 4. Aprobación del gasto principal ──
        self.client.force_login(self.coordinator)
        resp = self.client.post(reverse('expenses:approve', kwargs={'pk': expense_main.pk}))
        self.assertEqual(resp.status_code, 200)
        expense_main.refresh_from_db()
        self.assertEqual(expense_main.status, 'approved')
        self.assertTrue(
            AuditLog.objects.filter(action='approved', object_id=expense_main.pk).exists()
        )

        self._link_period(expense_main, expense_obs)

        # ── 5. Reportes PDF / Excel ──
        self.client.force_login(self.coordinator)
        resp = self.client.post(reverse('reports:patient_pdf'), {
            'patient_id': self.patient.pk,
            'period_id': self.period.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content[:4] == b'%PDF')

        resp = self.client.post(reverse('reports:site_pdf'), {
            'protocol_id': self.protocol.pk,
            'period_id': self.period.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

        resp = self.client.post(reverse('reports:site_excel'), {
            'protocol_id': self.protocol.pk,
            'period_id': self.period.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])

        # ── 6. Cierre de período e inmutabilidad ──
        self.client.force_login(self.coordinator)
        resp = self.client.post(reverse('periods:close', kwargs={'pk': self.period.pk}))
        self.assertIn(resp.status_code, [200, 302])
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'closed')

        expense_main.refresh_from_db()
        self.assertIn(expense_main.status, ('settled', 'exported'))

        pending = Expense.objects.create(
            visit=self.visit,
            period=self.period,
            category='transport',
            amount=Decimal('100.00'),
            expense_date=date(2025, 3, 10),
            status='pending_review',
            submitted_by=self.assistant,
        )
        resp = self.client.post(reverse('expenses:approve', kwargs={'pk': pending.pk}))
        self.assertEqual(resp.status_code, 422)

        # ── 7. Dashboards por rol ──
        for user, snippet in [
            (self.coordinator, b'Panel de coordinaci'),
            (self.assistant, b'Cargar nuevo ticket'),
            (self.auditor, b'solo lectura'),
            (self.admin, b'Panel de administraci'),
        ]:
            self.client.force_login(user)
            resp = self.client.get(reverse('dashboard:index'))
            self.assertEqual(resp.status_code, 200)
            self.assertIn(snippet, resp.content)

        # ── 8. Multisite: coordinador A no accede a site B ──
        self.client.force_login(self.coordinator)
        resp = self.client.post(reverse('periods:close', kwargs={'pk': self.period_b.pk}))
        self.assertEqual(resp.status_code, 404)

        resp = self.client.get(reverse('periods:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.period_b.name)

        resp = self.client.get(
            reverse('expenses:htmx_patients'),
            {'protocol': self.protocol_b.pk},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.patient_b.patient_code)

        # ── 9. Auditor: lectura OK, mutaciones bloqueadas ──
        self.client.force_login(self.auditor)
        resp = self.client.get(reverse('reports:index'))
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(reverse('expenses:detail', kwargs={'pk': expense_main.pk}))
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(reverse('expenses:approve', kwargs={'pk': expense_main.pk}))
        self.assertEqual(resp.status_code, 403)

        resp = self.client.post(reverse('periods:close', kwargs={'pk': self.period.pk}))
        self.assertEqual(resp.status_code, 403)
