from django import forms
from .models import Condominio, UF_CHOICES

class CondominioForm(forms.ModelForm):
    class Meta:
        model = Condominio
        fields = [
            "cnpj", "nome", "email",
            "cep", "numero", "logradouro", "bairro", "complemento",
            "municipio", "estado", "ativo",
        ]
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "contato@exemplo.com"}),
            "estado": forms.Select(attrs={"class": "form-select"}),
            "ativo": forms.CheckboxInput(),
        }

class CondominioFiltroForm(forms.Form):
    q = forms.CharField(label="Busca (nome, e-mail, CNPJ)", required=False)
    cidade = forms.CharField(label="Cidade", required=False)
    uf = forms.ChoiceField(
        label="UF", required=False,
        choices=[("", "--")] + list(UF_CHOICES)
    )
    ATIVOS_CHOICES = (("", "Todos"), ("1", "Ativos"), ("0", "Inativos"))
    ativos = forms.ChoiceField(choices=ATIVOS_CHOICES, required=False)

class ImportacaoExcelForm(forms.Form):
    arquivo = forms.FileField(label="Arquivo (.xlsx)")
    def clean_arquivo(self):
        f = self.cleaned_data["arquivo"]
        if not f.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Envie um arquivo .xlsx")
        return f
