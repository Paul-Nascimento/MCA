from django import forms
from .models import Modalidade

class ModalidadeForm(forms.ModelForm):
    class Meta:
        model = Modalidade
        fields = ["nome", "descricao", "ativo"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "ativo": forms.CheckboxInput(),
        }

class ModalidadeFiltroForm(forms.Form):
    q = forms.CharField(label="Busca (nome/descrição)", required=False)
    ATIVOS_CHOICES = (("", "Todos"), ("1", "Ativos"), ("0", "Inativos"))
    ativos = forms.ChoiceField(choices=ATIVOS_CHOICES, required=False)
