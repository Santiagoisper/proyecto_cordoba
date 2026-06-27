from django import forms
from django.utils import timezone
from .models import Expense, TicketFile

_INPUT = 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent'
_TEXTAREA = _INPUT + ' resize-none'


class ExpenseCreateForm(forms.Form):
    """Formulario de carga de gasto con ticket."""
    protocol = forms.IntegerField(widget=forms.HiddenInput())
    visit = forms.IntegerField(
        label='Visita',
        widget=forms.Select(attrs={'class': _INPUT, 'id': 'id_visit'})
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
        fields = ['category', 'amount', 'currency', 'expense_date', 'vendor', 'description']
        widgets = {
            'category': forms.Select(attrs={'class': _INPUT}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': _INPUT, 'placeholder': '0.00'}),
            'currency': forms.Select(
                choices=[('ARS', 'ARS — Pesos'), ('USD', 'USD — Dólares'), ('EUR', 'EUR — Euros')],
                attrs={'class': _INPUT},
            ),
            'vendor': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Nombre del comercio o proveedor'}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': _TEXTAREA,
                                                  'placeholder': 'Descripción adicional (opcional)'}),
        }
        labels = {
            'category': 'Categoría', 'amount': 'Monto', 'currency': 'Moneda',
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
        fields = ['category', 'amount', 'currency', 'expense_date', 'vendor', 'description']
        widgets = {
            'category': forms.Select(attrs={'class': _INPUT}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': _INPUT}),
            'currency': forms.Select(
                choices=[('ARS', 'ARS — Pesos'), ('USD', 'USD — Dólares'), ('EUR', 'EUR — Euros')],
                attrs={'class': _INPUT},
            ),
            'vendor': forms.TextInput(attrs={'class': _INPUT}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': _TEXTAREA}),
        }
        labels = {
            'category': 'Categoría', 'amount': 'Monto', 'currency': 'Moneda',
            'vendor': 'Comercio / Proveedor', 'description': 'Descripción',
        }
