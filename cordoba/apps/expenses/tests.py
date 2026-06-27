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

from apps.protocols.models import Protocol, VisitType
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
