from django import forms
from django.utils import timezone
from .models import Expense, TicketFile


class ExpenseCreateForm(forms.Form):
    """
    Formulario de carga de gasto con ticket.
    Los selects de paciente y visita se cargan dinámicamente vía HTMX.
    """
    protocol = forms.IntegerField(widget=forms.HiddenInput())
    visit = forms.IntegerField(
        label='Visita',
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'id': 'id_visit',
        })
    )
    category = forms.ChoiceField(
        label='Categoría',
        choices=Expense.CATEGORY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        })
    )
    expense_date = forms.DateField(
        label='Fecha del gasto',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        }),
        initial=timezone.now().date,
    )
    ticket_file = forms.ImageField(
        label='Foto del ticket',
        widget=forms.FileInput(attrs={
            'accept': 'image/*',
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
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Ej: Taxi al hospital, almuerzo reunión, etc.',
            'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none',
        })
    )


class ExpenseReviewForm(forms.ModelForm):
    """
    Formulario para revisar y corregir campos extraídos por OCR.
    El asistente puede editar cualquier campo antes de enviar al coordinador.
    """
    expense_date = forms.DateField(
        label='Fecha del ticket',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        })
    )

    class Meta:
        model = Expense
        fields = ['category', 'amount', 'currency', 'expense_date', 'vendor', 'description']
        widgets = {
            'category': forms.Select(attrs={
                'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            }),
            'amount': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': '0.00',
            }),
            'currency': forms.Select(
                choices=[('ARS', 'ARS — Pesos'), ('USD', 'USD — Dólares'), ('EUR', 'EUR — Euros')],
                attrs={
                    'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                }
            ),
            'vendor': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Nombre del comercio o proveedor',
            }),
            'description': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-3 py-2.5 rounded-lg border border-slate-300 text-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none',
                'placeholder': 'Descripción adicional (opcional)',
            }),
        }
        labels = {
            'category': 'Categoría',
            'amount': 'Monto',
            'currency': 'Moneda',
            'vendor': 'Comercio / Proveedor',
            'description': 'Descripción',
        }
