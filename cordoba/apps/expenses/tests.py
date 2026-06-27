"""
Tests críticos — Task #5: Cierre de período, auditoría y hardening.
Corre con: cd cordoba && python manage.py test apps.expenses.tests
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.protocols.models import Protocol, Site, VisitType
from apps.patients.models import Patient, Visit
from .models import Expense, ExpensePeriod, AuditLog
from .services import close_period, ExpenseValidationService

User = get_user_model()


# ─── Fixtures base ────────────────────────────────────────────────────────────

class BaseExpenseTestCase(TestCase):
    """Crea fixtures mínimos reutilizables por todos los tests."""

    @classmethod
    def setUpTestData(cls):
        Group.objects.get_or_create(name='coordinator')
        Group.objects.get_or_create(name='assistant')

        cls.coordinator = User.objects.create_user(
            username='coord_test', password='testpass123'
        )
        cls.coordinator.groups.add(Group.objects.get(name='coordinator'))

        cls.assistant = User.objects.create_user(
            username='asst_test', password='testpass123'
        )
        cls.assistant.groups.add(Group.objects.get(name='assistant'))

        cls.protocol = Protocol.objects.create(
            code='PROT-TEST-01',
            name='Protocolo de prueba',
            max_daily_meals=Decimal('2000.00'),
            max_daily_transport=Decimal('3000.00'),
            max_daily_accommodation=Decimal('10000.00'),
            created_by=cls.coordinator,
        )
        cls.visit_type = VisitType.objects.create(
            protocol=cls.protocol,
            name='Visita 1',
            code='V1',
            window_before_days=3,
            window_after_days=3,
        )
        cls.patient = Patient.objects.create(
            protocol=cls.protocol,
            patient_code='001-001',
            created_by=cls.coordinator,
        )
        cls.visit = Visit.objects.create(
            patient=cls.patient,
            visit_type=cls.visit_type,
            scheduled_date=date(2025, 3, 15),
            created_by=cls.coordinator,
        )
        cls.period = ExpensePeriod.objects.create(
            protocol=cls.protocol,
            name='Q1 2025',
            date_from=date(2025, 1, 1),
            date_to=date(2025, 3, 31),
            created_by=cls.coordinator,
        )

    def _make_expense(self, status='approved', amount=None, category='transport',
                      expense_date=None, period=None):
        """Helper: crea un gasto en el período por defecto."""
        return Expense.objects.create(
            visit=self.visit,
            period=period if period is not None else self.period,
            category=category,
            amount=amount or Decimal('500.00'),
            expense_date=expense_date or date(2025, 3, 15),
            status=status,
            submitted_by=self.assistant,
        )


# ─── Tests de close_period (service) ─────────────────────────────────────────

class ClosePeriodServiceTest(BaseExpenseTestCase):

    def setUp(self):
        self.period.status = 'open'
        self.period.closed_by = None
        self.period.closed_at = None
        self.period.save()

    def test_close_period_happy_path(self):
        """Cierre exitoso: approved→settled, AuditLog creado, closed_at seteado."""
        exp1 = self._make_expense(status='approved')
        exp2 = self._make_expense(status='approved', amount=Decimal('800.00'))

        period = close_period(self.period.pk, self.coordinator)

        self.assertEqual(period.status, 'closed')
        self.assertEqual(period.closed_by, self.coordinator)
        self.assertIsNotNone(period.closed_at)

        exp1.refresh_from_db()
        exp2.refresh_from_db()
        self.assertEqual(exp1.status, 'settled')
        self.assertEqual(exp2.status, 'settled')

        audit_count = AuditLog.objects.filter(
            action='period_closed',
            content_type='Expense',
        ).count()
        self.assertEqual(audit_count, 2)

        period_audit = AuditLog.objects.filter(
            action='period_closed',
            content_type='ExpensePeriod',
            object_id=period.pk,
        )
        self.assertTrue(period_audit.exists())
        self.assertEqual(period_audit.first().details['expenses_settled'], 2)

    def test_close_period_blocks_if_pending_review(self):
        """ValueError si hay gastos en pending_review."""
        self._make_expense(status='pending_review')

        with self.assertRaises(ValueError) as ctx:
            close_period(self.period.pk, self.coordinator)

        self.assertIn('pendiente', str(ctx.exception).lower())

        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'open')

    def test_close_period_already_closed(self):
        """ValueError si el período ya está cerrado."""
        self.period.status = 'closed'
        self.period.save()

        with self.assertRaises(ValueError) as ctx:
            close_period(self.period.pk, self.coordinator)

        self.assertIn('cerrado', str(ctx.exception).lower())

    def test_close_period_with_no_approved_expenses(self):
        """Cierre de período sin gastos aprobados (solo rechazados/observados)."""
        self._make_expense(status='rejected')
        self._make_expense(status='observed')

        period = close_period(self.period.pk, self.coordinator)

        self.assertEqual(period.status, 'closed')

        audit = AuditLog.objects.get(
            action='period_closed',
            content_type='ExpensePeriod',
            object_id=period.pk,
        )
        self.assertEqual(audit.details['expenses_settled'], 0)

    def test_close_period_does_not_touch_expenses_outside_period(self):
        """Gastos sin FK al período no deben verse afectados."""
        other_period = ExpensePeriod.objects.create(
            protocol=self.protocol,
            name='Q2 2025',
            date_from=date(2025, 4, 1),
            date_to=date(2025, 6, 30),
            created_by=self.coordinator,
        )
        exp_other = self._make_expense(status='approved', period=other_period)

        close_period(self.period.pk, self.coordinator)

        exp_other.refresh_from_db()
        self.assertEqual(exp_other.status, 'approved')

    def test_close_period_atomic_rollback_on_error(self):
        """Si algo falla a mitad, la transacción se revierte."""
        self._make_expense(status='approved')

        period_id = self.period.pk

        import unittest.mock as mock
        with mock.patch(
            'apps.expenses.models.AuditLog.objects.bulk_create',
            side_effect=Exception("DB error simulado"),
        ):
            with self.assertRaises(Exception):
                close_period(period_id, self.coordinator)

        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'open')


# ─── Tests del endpoint HTTP ──────────────────────────────────────────────────

class ClosePeriodViewTest(BaseExpenseTestCase):

    def setUp(self):
        self.period.status = 'open'
        self.period.closed_by = None
        self.period.closed_at = None
        self.period.save()
        self.client = Client()

    def test_close_period_requires_login(self):
        url = reverse('periods:close', kwargs={'pk': self.period.pk})
        resp = self.client.post(url)
        self.assertIn(resp.status_code, [302, 403])

    def test_close_period_forbidden_for_assistant(self):
        self.client.force_login(self.assistant)
        url = reverse('periods:close', kwargs={'pk': self.period.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_close_period_forbidden_with_get(self):
        self.client.force_login(self.coordinator)
        url = reverse('periods:close', kwargs={'pk': self.period.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)

    def test_close_period_ok_coordinator(self):
        self._make_expense(status='approved')
        self.client.force_login(self.coordinator)
        url = reverse('periods:close', kwargs={'pk': self.period.pk})
        resp = self.client.post(url)
        self.assertIn(resp.status_code, [200, 302])
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'closed')

    def test_close_period_htmx_returns_partial(self):
        self._make_expense(status='approved')
        self.client.force_login(self.coordinator)
        url = reverse('periods:close', kwargs={'pk': self.period.pk})
        resp = self.client.post(url, HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'period-row-')

    def test_close_period_htmx_error_on_pending(self):
        self._make_expense(status='pending_review')
        self.client.force_login(self.coordinator)
        url = reverse('periods:close', kwargs={'pk': self.period.pk})
        resp = self.client.post(url, HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 422)
        self.assertIn(b'pendiente', resp.content.lower())

    def test_period_list_requires_coordinator(self):
        self.client.force_login(self.assistant)
        url = reverse('periods:list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_period_list_ok_for_coordinator(self):
        self.client.force_login(self.coordinator)
        url = reverse('periods:list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Q1 2025')


# ─── Tests de validación de gastos ───────────────────────────────────────────

class ExpenseValidationTest(BaseExpenseTestCase):

    def test_amount_exceeds_cap_meals(self):
        """Alerta error si monto de comidas supera tope diario."""
        expense = self._make_expense(
            status='approved',
            category='meals',
            amount=Decimal('3000.00'),
        )
        svc = ExpenseValidationService()
        alerts = svc.validate(expense)
        codes = [a.code for a in alerts]
        self.assertIn('amount_exceeds_cap', codes)
        self.assertEqual(next(a.level for a in alerts if a.code == 'amount_exceeds_cap'), 'error')

    def test_amount_within_cap_no_alert(self):
        """Sin alerta si el monto está dentro del tope."""
        expense = self._make_expense(
            status='approved',
            category='meals',
            amount=Decimal('1500.00'),
        )
        svc = ExpenseValidationService()
        alerts = svc.validate(expense)
        self.assertNotIn('amount_exceeds_cap', [a.code for a in alerts])

    def test_duplicate_detection(self):
        """Alerta de posible duplicado si ya existe gasto idéntico."""
        exp1 = self._make_expense(status='approved', amount=Decimal('500.00'))
        exp2 = self._make_expense(status='pending_review', amount=Decimal('500.00'))

        svc = ExpenseValidationService()
        alerts = svc.validate(exp2)
        self.assertIn('possible_duplicate', [a.code for a in alerts])

    def test_duplicate_ignores_rejected(self):
        """El duplicado rechazado no genera alerta."""
        self._make_expense(status='rejected', amount=Decimal('500.00'))
        exp2 = self._make_expense(status='pending_review', amount=Decimal('500.00'))

        svc = ExpenseValidationService()
        alerts = svc.validate(exp2)
        self.assertNotIn('possible_duplicate', [a.code for a in alerts])


# ─── Tests de inmutabilidad de AuditLog ──────────────────────────────────────

class AuditLogImmutabilityTest(BaseExpenseTestCase):

    def test_auditlog_cannot_be_modified_via_admin(self):
        """AuditLog.has_change_permission siempre retorna False."""
        from apps.expenses.admin import AuditLogAdmin
        from django.contrib.admin.sites import AdminSite

        site = AdminSite()
        admin_obj = AuditLogAdmin(AuditLog, site)
        self.assertFalse(admin_obj.has_change_permission(None))
        self.assertFalse(admin_obj.has_delete_permission(None))
        self.assertFalse(admin_obj.has_add_permission(None))

    def test_auditlog_created_on_approve(self):
        """Se crea AuditLog al aprobar un gasto via view."""
        expense = self._make_expense(status='pending_review')
        self.client = Client()
        self.client.force_login(self.coordinator)

        url = reverse('expenses:approve', kwargs={'pk': expense.pk})
        self.client.post(url, {'notes': ''})

        expense.refresh_from_db()
        self.assertEqual(expense.status, 'approved')
        log = AuditLog.objects.filter(
            action='approved',
            content_type='Expense',
            object_id=expense.pk,
        )
        self.assertTrue(log.exists())


# ─── Tests de inmutabilidad de período cerrado ────────────────────────────────

class ClosedPeriodImmutabilityTest(BaseExpenseTestCase):
    """Verifica que no se puedan mutar gastos pertenecientes a un período cerrado."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.closed_period = ExpensePeriod.objects.create(
            protocol=cls.protocol,
            name='Período Cerrado Test',
            date_from=date(2024, 10, 1),
            date_to=date(2024, 12, 31),
            status='closed',
            closed_by=cls.coordinator,
            closed_at=timezone.now(),
            created_by=cls.coordinator,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.coordinator)

    def _make_closed_expense(self, status='pending_review'):
        return Expense.objects.create(
            visit=self.visit,
            period=self.closed_period,
            category='transport',
            amount=Decimal('400.00'),
            expense_date=date(2024, 11, 10),
            status=status,
            submitted_by=self.assistant,
        )

    def test_approve_blocked_for_closed_period(self):
        """approve_expense retorna 422 si el período está cerrado."""
        expense = self._make_closed_expense(status='pending_review')
        url = reverse('expenses:approve', kwargs={'pk': expense.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 422)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'pending_review')

    def test_reject_blocked_for_closed_period(self):
        """reject_expense retorna 422 si el período está cerrado."""
        expense = self._make_closed_expense(status='pending_review')
        url = reverse('expenses:reject', kwargs={'pk': expense.pk})
        resp = self.client.post(url, {'notes': 'test'})
        self.assertEqual(resp.status_code, 422)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'pending_review')

    def test_observe_blocked_for_closed_period(self):
        """observe_expense retorna 422 si el período está cerrado."""
        expense = self._make_closed_expense(status='pending_review')
        url = reverse('expenses:observe', kwargs={'pk': expense.pk})
        resp = self.client.post(url, {'notes': 'test'})
        self.assertEqual(resp.status_code, 422)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'pending_review')

    def test_correct_blocked_for_closed_period(self):
        """expense_correct redirige con error si el período está cerrado."""
        expense = self._make_closed_expense(status='observed')
        self.client.force_login(self.assistant)
        url = reverse('expenses:correct', kwargs={'pk': expense.pk})
        resp = self.client.post(url, {'description': 'nueva desc'})
        self.assertIn(resp.status_code, [302, 200])
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'observed')

    def test_second_close_on_same_period_blocked(self):
        """close_period falla si se intenta cerrar un período ya cerrado."""
        with self.assertRaises(ValueError) as ctx:
            close_period(self.closed_period.pk, self.coordinator)
        self.assertIn('cerrado', str(ctx.exception).lower())


# ─── Multisite IDOR isolation ──────────────────────────────────────────────────

class MultisiteIsolationTest(TestCase):
    """
    Coordinador de site_a NO puede ver ni mutar objetos de site_b.
    Protección IDOR: todas las respuestas deben ser 403 o 404.
    """

    @classmethod
    def setUpTestData(cls):
        Group.objects.get_or_create(name='coordinator')

        cls.site_a = Site.objects.create(code='SITE-A', name='Centro A')
        cls.site_b = Site.objects.create(code='SITE-B', name='Centro B')

        cls.coord_a = User.objects.create_user(username='coord_a', password='pass')
        cls.coord_a.groups.add(Group.objects.get(name='coordinator'))
        cls.coord_a.site = cls.site_a
        cls.coord_a.save()

        cls.coord_b = User.objects.create_user(username='coord_b', password='pass')
        cls.coord_b.groups.add(Group.objects.get(name='coordinator'))
        cls.coord_b.site = cls.site_b
        cls.coord_b.save()

        cls.protocol_b = Protocol.objects.create(
            code='PROT-B-01',
            name='Protocolo del site B',
            site=cls.site_b,
            max_daily_meals=Decimal('2000.00'),
            max_daily_transport=Decimal('3000.00'),
            max_daily_accommodation=Decimal('10000.00'),
            created_by=cls.coord_b,
        )
        cls.visit_type_b = VisitType.objects.create(
            protocol=cls.protocol_b,
            name='Visita B1',
            code='VB1',
            window_before_days=3,
            window_after_days=3,
        )
        cls.patient_b = Patient.objects.create(
            protocol=cls.protocol_b,
            patient_code='B01-001',
            created_by=cls.coord_b,
        )
        cls.visit_b = Visit.objects.create(
            patient=cls.patient_b,
            visit_type=cls.visit_type_b,
            scheduled_date=date(2025, 3, 15),
            created_by=cls.coord_b,
        )
        cls.period_b = ExpensePeriod.objects.create(
            protocol=cls.protocol_b,
            name='Q1 2025 B',
            date_from=date(2025, 1, 1),
            date_to=date(2025, 3, 31),
            created_by=cls.coord_b,
        )
        cls.expense_b = Expense.objects.create(
            visit=cls.visit_b,
            category='transport',
            amount=Decimal('500.00'),
            expense_date=date(2025, 3, 15),
            description='Taxi',
            status='pending_review',
            submitted_by=cls.coord_b,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.coord_a)

    def test_coord_a_cannot_view_expense_detail_from_site_b(self):
        """expense_detail retorna 404 para coordinador de otro site."""
        url = reverse('expenses:detail', kwargs={'pk': self.expense_b.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_coord_a_cannot_approve_expense_from_site_b(self):
        """approve_expense retorna 404 para gasto de otro site."""
        url = reverse('expenses:approve', kwargs={'pk': self.expense_b.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 404)

    def test_coord_a_cannot_reject_expense_from_site_b(self):
        """reject_expense retorna 404 para gasto de otro site."""
        url = reverse('expenses:reject', kwargs={'pk': self.expense_b.pk})
        resp = self.client.post(url, {'notes': 'intento cruzado'})
        self.assertEqual(resp.status_code, 404)

    def test_coord_a_cannot_observe_expense_from_site_b(self):
        """observe_expense retorna 404 para gasto de otro site."""
        url = reverse('expenses:observe', kwargs={'pk': self.expense_b.pk})
        resp = self.client.post(url, {'notes': 'intento cruzado'})
        self.assertEqual(resp.status_code, 404)

    def test_coord_a_cannot_close_period_from_site_b(self):
        """close_period_view retorna 404 para período de otro site."""
        url = reverse('periods:close', kwargs={'pk': self.period_b.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 404)

    def test_period_list_excludes_site_b_periods(self):
        """period_list no muestra períodos de otro site."""
        url = reverse('periods:list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.period_b.name)

    def test_htmx_patients_cross_site_returns_empty(self):
        """htmx_patients_for_protocol retorna lista vacía para protocolo de otro site."""
        url = reverse('expenses:htmx_patients')
        resp = self.client.get(url, {'protocol': self.protocol_b.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.patient_b.patient_code)

    def test_htmx_visits_cross_site_returns_empty(self):
        """htmx_visits_for_patient retorna lista vacía para paciente de otro site."""
        url = reverse('expenses:htmx_visits')
        resp = self.client.get(url, {'patient': self.patient_b.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.visit_type_b.name)

    def test_expense_create_cross_site_patient_is_forbidden(self):
        """expense_create POST con patient de otro site retorna 403 sin crear el gasto."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_image = SimpleUploadedFile(
            'ticket.jpg', b'\xff\xd8\xff\xe0' + b'\x00' * 20, content_type='image/jpeg'
        )
        count_before = Expense.objects.filter(visit__patient=self.patient_b).count()
        url = reverse('expenses:create')
        resp = self.client.post(url, {
            'protocol': self.protocol_b.pk,
            'patient': self.patient_b.pk,
            'visit_type_id': self.visit_type_b.pk,
            'category': 'transport',
            'expense_date': '2025-03-15',
            'description': 'Intento cruzado',
            'ticket_file': fake_image,
        })
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Expense.objects.filter(visit__patient=self.patient_b).count(), count_before)

    def test_report_site_pdf_cross_site_is_blocked(self):
        """site_pdf retorna 404 para protocolo de otro site."""
        url = reverse('reports:site_pdf')
        resp = self.client.post(url, {
            'protocol_id': self.protocol_b.pk,
            'period_id': self.period_b.pk,
        })
        self.assertEqual(resp.status_code, 404)

    def test_report_patient_pdf_cross_site_is_blocked(self):
        """patient_pdf retorna 404 para paciente de otro site."""
        url = reverse('reports:patient_pdf')
        resp = self.client.post(url, {
            'patient_id': self.patient_b.pk,
            'period_id': self.period_b.pk,
        })
        self.assertEqual(resp.status_code, 404)

    def test_report_site_excel_cross_site_is_blocked(self):
        """site_excel retorna 404 para protocolo de otro site."""
        url = reverse('reports:site_excel')
        resp = self.client.post(url, {
            'protocol_id': self.protocol_b.pk,
            'period_id': self.period_b.pk,
        })
        self.assertEqual(resp.status_code, 404)

    def test_report_htmx_patients_cross_site_returns_empty(self):
        """htmx_patients (reports) retorna lista vacía para protocolo de otro site."""
        url = reverse('reports:htmx_patients')
        resp = self.client.get(url, {'protocol': self.protocol_b.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.patient_b.patient_code)

    def test_report_htmx_periods_cross_site_returns_empty(self):
        """htmx_periods (reports) retorna lista vacía para protocolo de otro site."""
        url = reverse('reports:htmx_periods')
        resp = self.client.get(url, {'protocol': self.protocol_b.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.period_b.name)


class VisitLockingTest(BaseExpenseTestCase):
    """
    Verifica que una visita quede bloqueada cuando tiene un comprobante activo,
    y se desbloquee si ese comprobante es rechazado.
    """

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.assistant)

    def _post_expense(self, visit_type=None, patient=None):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_image = SimpleUploadedFile(
            'ticket.jpg', b'\xff\xd8\xff\xe0' + b'\x00' * 20, content_type='image/jpeg'
        )
        vt = visit_type or self.visit_type
        pat = patient or self.patient
        url = reverse('expenses:create')
        return self.client.post(url, {
            'protocol': pat.protocol.pk,
            'patient': pat.pk,
            'visit_type_id': vt.pk,
            'category': 'transport',
            'expense_date': '2025-03-15',
            'description': 'Taxi al hospital',
            'ticket_file': fake_image,
        })

    def test_htmx_visits_returns_visit_types_for_patient(self):
        """htmx_visits_for_patient devuelve tipos de visita del protocolo."""
        url = reverse('expenses:htmx_visits')
        resp = self.client.get(url, {'patient': self.patient.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.visit_type.name)

    def test_htmx_protocol_info_returns_summary(self):
        """htmx_protocol_info devuelve sponsor, fase y tipos de visita."""
        url = reverse('expenses:htmx_protocol_info')
        resp = self.client.get(url, {'protocol': self.protocol.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.visit_type.name)

    def test_second_expense_on_same_visit_is_blocked(self):
        """
        Cargar un segundo comprobante para la misma visita del mismo paciente
        debe retornar 200 con error (no redirige ni crea gasto).
        """
        # Primer gasto — debe redirigir a review
        resp1 = self._post_expense()
        self.assertEqual(resp1.status_code, 302)
        self.assertEqual(Expense.objects.filter(visit__patient=self.patient, visit__visit_type=self.visit_type).count(), 1)

        # Segundo intento — debe rechazarse con mensaje de error
        resp2 = self._post_expense()
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, 'ya tiene un comprobante cargado')
        self.assertEqual(Expense.objects.filter(visit__patient=self.patient, visit__visit_type=self.visit_type).count(), 1)

    def test_visit_unlocks_after_rejection(self):
        """
        Si el comprobante activo es rechazado, la visita vuelve a estar disponible
        y se puede cargar un nuevo comprobante.
        """
        # Primer gasto
        resp1 = self._post_expense()
        self.assertEqual(resp1.status_code, 302)
        expense = Expense.objects.filter(visit__patient=self.patient, visit__visit_type=self.visit_type).first()

        # Rechazar el gasto
        expense.status = 'rejected'
        expense.save(update_fields=['status'])

        # Segundo intento — ahora debe poder crearse
        resp2 = self._post_expense()
        self.assertEqual(resp2.status_code, 302)
        self.assertEqual(Expense.objects.filter(visit__patient=self.patient, visit__visit_type=self.visit_type).count(), 2)

    def test_htmx_visits_shows_locked_for_active_expense(self):
        """
        Cuando la visita tiene un comprobante activo, el endpoint marca esa visita
        como bloqueada en el HTML (contiene 'ya tiene comprobante').
        """
        # Crear el gasto para bloquear la visita
        Expense.objects.create(
            visit=self.visit,
            category='transport',
            amount=500,
            expense_date=date(2025, 3, 15),
            status='pending_review',
            submitted_by=self.assistant,
        )
        url = reverse('expenses:htmx_visits')
        resp = self.client.get(url, {'patient': self.patient.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ya tiene comprobante')

    def test_htmx_visits_unlocked_after_rejection(self):
        """
        Si todos los comprobantes de una visita son rechazados, la visita
        no aparece como bloqueada en el endpoint HTMX.
        """
        Expense.objects.create(
            visit=self.visit,
            category='transport',
            amount=500,
            expense_date=date(2025, 3, 15),
            status='rejected',
            submitted_by=self.assistant,
        )
        url = reverse('expenses:htmx_visits')
        resp = self.client.get(url, {'patient': self.patient.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'ya tiene comprobante')


# ─── Tests de visit_actual_date end-to-end ────────────────────────────────────

class VisitActualDateTest(BaseExpenseTestCase):
    """
    Verifica que el campo visit_actual_date del formulario de carga se persiste
    correctamente en Visit.actual_date y se actualiza cuando la visita ya existe.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.visit_type_date = VisitType.objects.create(
            protocol=cls.protocol,
            name='Visita Fecha Test',
            code='VFT',
            window_before_days=3,
            window_after_days=3,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.assistant)

    def _post_create(self, visit_actual_date=None):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_image = SimpleUploadedFile(
            'ticket.jpg', b'\xff\xd8\xff\xe0' + b'\x00' * 20, content_type='image/jpeg'
        )
        data = {
            'protocol': self.patient.protocol.pk,
            'patient': self.patient.pk,
            'visit_type_id': self.visit_type_date.pk,
            'category': 'transport',
            'expense_date': '2025-03-15',
            'description': 'Taxi al hospital',
            'ticket_file': fake_image,
        }
        if visit_actual_date:
            data['visit_actual_date'] = visit_actual_date
        return self.client.post(reverse('expenses:create'), data)

    def test_visit_actual_date_saved_when_provided(self):
        """
        Al enviar visit_actual_date en el formulario, ese valor se persiste
        como Visit.actual_date en la base de datos.
        """
        resp = self._post_create(visit_actual_date='2025-03-20')
        self.assertEqual(resp.status_code, 302)
        visit = Visit.objects.get(patient=self.patient, visit_type=self.visit_type_date)
        self.assertEqual(visit.actual_date, date(2025, 3, 20))

    def test_visit_created_valid_without_actual_date(self):
        """
        Al omitir visit_actual_date, la visita se crea correctamente y
        actual_date queda en None.
        """
        resp = self._post_create()
        self.assertEqual(resp.status_code, 302)
        visit = Visit.objects.get(patient=self.patient, visit_type=self.visit_type_date)
        self.assertIsNone(visit.actual_date)

    def test_existing_visit_actual_date_updated(self):
        """
        Si la visita ya existe (get_or_create devuelve created=False),
        visit_actual_date actualiza Visit.actual_date correctamente.
        """
        Visit.objects.create(
            patient=self.patient,
            visit_type=self.visit_type_date,
            scheduled_date=date(2025, 3, 15),
            actual_date=None,
            created_by=self.coordinator,
        )
        resp = self._post_create(visit_actual_date='2025-04-01')
        self.assertEqual(resp.status_code, 302)
        visit = Visit.objects.get(patient=self.patient, visit_type=self.visit_type_date)
        self.assertEqual(visit.actual_date, date(2025, 4, 1))
