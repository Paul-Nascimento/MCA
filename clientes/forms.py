# clientes/forms.py
from django import forms
from .models import Cliente, UF_CHOICES
from condominios.models import Condominio

class ClienteForm(forms.ModelForm):
    condominio = forms.ModelChoiceField(
        queryset=Condominio.objects.filter(ativo=True).order_by("nome"),
        required=True,
        label="Condomínio",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = Cliente
        fields = [
            "cpf_cnpj","nome_razao","data_nascimento","telefone_emergencial","telefone_celular",
            "cep","numero_id","logradouro","bairro","complemento","municipio","estado","email",
              "condominio"  # <- adicionado aqui
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type":"date"}),
        }

class ClienteFiltroForm(forms.Form):
    q = forms.CharField(required=False, label="Busca")
    ATIVOS_CHOICES = (("", "Todos"), ("1","Ativos"), ("0","Inativos"))
    ativos = forms.ChoiceField(choices=ATIVOS_CHOICES, required=False)

    # (opcional) filtro por condomínio:
    condominio = forms.ModelChoiceField(
        queryset=Condominio.objects.filter(ativo=True).order_by("nome"),
        required=False, label="Condomínio",
        widget=forms.Select(attrs={"class": "form-select"})
    )
