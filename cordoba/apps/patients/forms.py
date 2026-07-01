from django import forms
from .models import Patient, Visit


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['protocol', 'patient_code', 'initials', 'enrolled_date', 'is_active']
        widgets = {
            'protocol': forms.Select(attrs={'class': 'block w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'patient_code': forms.TextInput(attrs={'class': 'block w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent', 'placeholder': 'Ej: 001-001'}),
            'initials': forms.TextInput(attrs={'class': 'block w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent', 'placeholder': 'Iniciales'}),
            'enrolled_date': forms.DateInput(attrs={'type': 'date', 'class': 'block w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'h-4 w-4'}),
        }


class VisitForm(forms.ModelForm):
    class Meta:
        model = Visit
        fields = ['patient', 'visit_type', 'scheduled_date', 'actual_date', 'status', 'notes']
        widgets = {
            'patient': forms.Select(attrs={'class': 'block w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'visit_type': forms.Select(attrs={'class': 'block w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'scheduled_date': forms.DateInput(attrs={'type': 'date', 'class': 'block w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'actual_date': forms.DateInput(attrs={'type': 'date', 'class': 'block w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'status': forms.Select(attrs={'class': 'block w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'block w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent', 'placeholder': 'Notas opcionales'}),
        }
