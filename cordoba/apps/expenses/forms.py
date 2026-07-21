from django import forms
from django.utils import timezone
from .models import Expense, TicketFile, ReceptionTicket
from .validators import validate_ticket_file

_INPUT = 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent'
_TEXTAREA = _INPUT + ' resize-none'


class ExpenseCreateForm(forms.Form):
    """Formulario de carga de gasto con ticket."""
    protocol = forms.IntegerField(widget=forms.HiddenInput())
    visit_type_id = forms.IntegerField(
        label='Visita',
        widget=forms.Select(attrs={'class': _INPUT, 'id': 'id_visit_type_id'})
    )
    visit_actual_date = forms.DateField(
        label='Fecha real de la visita',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': _INPUT, 'id': 'id_visit_actual_date'}),
    )
    category = forms.ChoiceField(
        label='Categoría',
        choices=Expense.CATEGORY_CHOICES,
        widget=forms.Select(attrs={'class': _INPUT}),
    )
    expense_date = forms.DateField(
        label='Fecha del gasto',
        widget=forms.DateInput(attrs={'type': 'date', 'class': _INPUT}),
        initial=timezone.now().date,
    )
    ticket_file = forms.FileField(
        label='Foto o PDF del ticket',
        widget=forms.FileInput(attrs={
            'accept': 'image/*,application/pdf',
            'capture': 'environment',
            'class': 'hidden',
            'id': 'ticket-file-input',
        }),
        required=True,
        validators=[validate_ticket_file],
    )
    description = forms.CharField(
        label='Descripción (opcional)',
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 2, 'class': _TEXTAREA,
                                      'placeholder': 'Ej: Taxi al hospital, almuerzo reunión...'}),
    )


class ExpenseReviewForm(forms.ModelForm):
    """Formulario de revisión y corrección de datos OCR."""
    expense_date = forms.DateField(
        label='Fecha del ticket',
        widget=forms.DateInput(attrs={'type': 'date', 'class': _INPUT}),
    )

    class Meta:
        model = Expense
        fields = [
            'category', 'amount', 'currency', 'exchange_rate_to_usd',
            'expense_date', 'vendor', 'description',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': _INPUT}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': _INPUT, 'placeholder': '0.00'}),
            'currency': forms.Select(
                choices=[('ARS', 'ARS — Pesos'), ('USD', 'USD — Dólares'), ('EUR', 'EUR — Euros')],
                attrs={'class': _INPUT},
            ),
            'exchange_rate_to_usd': forms.NumberInput(attrs={
                'step': '0.0001',
                'min': '0',
                'class': _INPUT,
                'placeholder': 'Ej: 1200.00',
            }),
            'vendor': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Nombre del comercio o proveedor'}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': _TEXTAREA,
                                                  'placeholder': 'Descripción adicional (opcional)'}),
        }
        labels = {
            'category': 'Categoría', 'amount': 'Monto', 'currency': 'Moneda',
            'exchange_rate_to_usd': 'Tipo de cambio a USD',
            'vendor': 'Comercio / Proveedor', 'description': 'Descripción',
        }


class ObservedCorrectionForm(forms.ModelForm):
    """
    Formulario para que el asistente corrija un gasto 'observed'.
    Solo permite editar campos que no cambian la trazabilidad del gasto.
    """
    expense_date = forms.DateField(
        label='Fecha del ticket',
        widget=forms.DateInput(attrs={'type': 'date', 'class': _INPUT}),
    )

    class Meta:
        model = Expense
        fields = [
            'category', 'amount', 'currency', 'exchange_rate_to_usd',
            'expense_date', 'vendor', 'description',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': _INPUT}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': _INPUT}),
            'currency': forms.Select(
                choices=[('ARS', 'ARS — Pesos'), ('USD', 'USD — Dólares'), ('EUR', 'EUR — Euros')],
                attrs={'class': _INPUT},
            ),
            'exchange_rate_to_usd': forms.NumberInput(attrs={
                'step': '0.0001',
                'min': '0',
                'class': _INPUT,
            }),
            'vendor': forms.TextInput(attrs={'class': _INPUT}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': _TEXTAREA}),
        }
        labels = {
            'category': 'Categoría', 'amount': 'Monto', 'currency': 'Moneda',
            'exchange_rate_to_usd': 'Tipo de cambio a USD',
            'vendor': 'Comercio / Proveedor', 'description': 'Descripción',
        }


class ReceptionTicketUploadForm(forms.ModelForm):
    """Carga rápida de comprobante en recepción, sin imputación clínica."""

    def clean_file(self):
        uploaded = self.cleaned_data['file']
        validate_ticket_file(uploaded)
        return uploaded

    class Meta:
        model = ReceptionTicket
        fields = ['file', 'notes']
        widgets = {
            'file': forms.FileInput(attrs={
                'accept': 'image/*,application/pdf',
                'capture': 'environment',
                'class': 'hidden',
                'id': 'ticket-file-input',
            }),
            'notes': forms.Textarea(attrs={
                'rows': 2,
                'class': _TEXTAREA,
                'placeholder': 'Observación opcional de recepción',
            }),
        }
        labels = {
            'file': 'Foto o PDF del comprobante',
            'notes': 'Observación',
        }


class ReceptionTicketAssignForm(forms.Form):
    """Formulario para imputar un ticket de recepción al flujo de gastos."""
    protocol = forms.IntegerField(widget=forms.HiddenInput())
    visit_type_id = forms.IntegerField(
        label='Visita',
        widget=forms.Select(attrs={'class': _INPUT, 'id': 'id_visit_type_id'}),
    )
    visit_actual_date = forms.DateField(
        label='Fecha real de la visita',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': _INPUT, 'id': 'id_visit_actual_date'}),
    )
    category = forms.ChoiceField(
        label='Categoría',
        choices=Expense.CATEGORY_CHOICES,
        widget=forms.Select(attrs={'class': _INPUT}),
    )
    expense_date = forms.DateField(
        label='Fecha del gasto',
        widget=forms.DateInput(attrs={'type': 'date', 'class': _INPUT}),
        initial=timezone.now().date,
    )
    description = forms.CharField(
        label='Descripción (opcional)',
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 2, 'class': _TEXTAREA}),
    )
