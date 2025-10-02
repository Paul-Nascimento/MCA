# modalidades/forms.py
from django import forms
from .models import Modalidade
# ADICIONE:
from condominios.models import Condominio

class ModalidadeForm(forms.ModelForm):
    # NOVO: exige condomínio
    condominio = forms.ModelChoiceField(
        queryset=Condominio.objects.filter(ativo=True).order_by("nome"),
        required=True,
        label="Condomínio",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = Modalidade
        fields = ["nome", "descricao", "ativo", "condominio"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "ativo": forms.CheckboxInput(),
        }

class ModalidadeFiltroForm(forms.Form):
    q = forms.CharField(label="Busca (nome/descrição)", required=False)
    ATIVOS_CHOICES = (("", "Todos"), ("1", "Ativos"), ("0", "Inativos"))
    ativos = forms.ChoiceField(choices=ATIVOS_CHOICES, required=False)

    # NOVO: filtro por condomínio (opcional)
    condominio = forms.ModelChoiceField(
        queryset=Condominio.objects.filter(ativo=True).order_by("nome"),
        required=False, label="Condomínio",
        widget=forms.Select(attrs={"class":"form-select"})
    )
