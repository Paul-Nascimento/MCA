from django import forms
from .models import ParametroContrato

class ParametroContratoForm(forms.ModelForm):
    class Meta:
        model = ParametroContrato
        fields = ["nome", "assunto_email", "corpo_email", "corpo_contrato", "ativo"]
        widgets = {
            "corpo_email": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
            "corpo_contrato": forms.Textarea(attrs={"rows": 12, "class": "form-control"}),
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "assunto_email": forms.TextInput(attrs={"class": "form-control"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
