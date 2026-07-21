"""
Tests de las vistas del dashboard reescritas: dashboard del auditor,
actualización de topes de viáticos y export CSV de visitas.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from django.urls import reverse

from apps.protocols.models import Site, Protocol
from apps.patients.models import Patient

User = get_user_model()


class DashboardAuditorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for name in ('coordinator', 'assistant', 'site_admin', 'auditor'):
            Group.objects.get_or_create(name=name)

        cls.site_a = Site.objects.create(code='SITE-A', name='Site A')
        cls.site_b = Site.objects.create(code='SITE-B', name='Site B')

        cls.protocol_a = Protocol.objects.create(code='P-A', name='Proto A', site=cls.site_a)
        cls.protocol_b = Protocol.objects.create(code='P-B', name='Proto B', site=cls.site_b)

        cls.patient_a = Patient.objects.create(
            protocol=cls.protocol_a, patient_code='001', viatic_cap=Decimal('10000'),
        )
        cls.patient_b = Patient.objects.create(
            protocol=cls.protocol_b, patient_code='002', viatic_cap=Decimal('5000'),
        )

        # Auditor con site (modelo fail-closed: acceso global = superuser/site_admin).
        cls.auditor = User.objects.create_user('auditor1', password='x', site=cls.site_a)
        cls.auditor.groups.add(Group.objects.get(name='auditor'))

        # Superadmin: acceso global a todos los sites.
        cls.superadmin = User.objects.create_superuser('root', password='x')

        cls.coord_a = User.objects.create_user('coorda', password='x', site=cls.site_a)
        cls.coord_a.groups.add(Group.objects.get(name='coordinator'))

    def setUp(self):
        self.client = Client()

    def test_auditor_dashboard_renders_scoped_to_site(self):
        """Auditor con site solo ve pacientes de su site."""
        self.client.force_login(self.auditor)
        resp = self.client.get(reverse('dashboard:auditor_viaticos'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_patients'], 1)

    def test_superadmin_dashboard_sees_all_sites(self):
        self.client.force_login(self.superadmin)
        resp = self.client.get(reverse('dashboard:auditor_viaticos'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_patients'], 2)

    def test_update_cap_valid(self):
        self.client.force_login(self.auditor)
        url = reverse('dashboard:update_viatic_cap', kwargs={'patient_id': self.patient_a.pk})
        resp = self.client.post(url, {'viatic_cap': '12345.50'})
        self.assertEqual(resp.status_code, 200)
        self.patient_a.refresh_from_db()
        self.assertEqual(self.patient_a.viatic_cap, Decimal('12345.50'))

    def test_update_cap_invalid_value(self):
        self.client.force_login(self.auditor)
        url = reverse('dashboard:update_viatic_cap', kwargs={'patient_id': self.patient_a.pk})
        resp = self.client.post(url, {'viatic_cap': 'no-numero'})
        self.assertEqual(resp.status_code, 400)

    def test_update_cap_negative_rejected(self):
        self.client.force_login(self.auditor)
        url = reverse('dashboard:update_viatic_cap', kwargs={'patient_id': self.patient_a.pk})
        resp = self.client.post(url, {'viatic_cap': '-100'})
        self.assertEqual(resp.status_code, 400)

    def test_update_cap_get_not_allowed(self):
        self.client.force_login(self.auditor)
        url = reverse('dashboard:update_viatic_cap', kwargs={'patient_id': self.patient_a.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)

    def test_coordinator_cannot_update_cap_other_site(self):
        """IDOR: coordinador del site A no puede tocar un paciente del site B."""
        self.client.force_login(self.coord_a)
        url = reverse('dashboard:update_viatic_cap', kwargs={'patient_id': self.patient_b.pk})
        resp = self.client.post(url, {'viatic_cap': '999'})
        self.assertIn(resp.status_code, (403, 404))
        self.patient_b.refresh_from_db()
        self.assertEqual(self.patient_b.viatic_cap, Decimal('5000'))

    def test_export_visits_csv_permission(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse('dashboard:export_visits_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
