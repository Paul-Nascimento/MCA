from django import forms
from .models import Funcionario

class FuncionarioForm(forms.ModelForm):
    class Meta:
        model = Funcionario
        fields = ["cpf_cnpj","nome", "email", "regime_trabalhista", "ativo"]  # + outros campos que você já usa
        widgets = {
            "regime_trabalhista": forms.Select(choices=Funcionario.RegimeTrabalhista.choices),
        }


class FuncionarioFiltroForm(forms.Form):
    q = forms.CharField(label="Busca (nome, e-mail, CPF/CNPJ)", required=False)
    ATIVOS_CHOICES = (("", "Todos"), ("1", "Ativos"), ("0", "Inativos"))
    ativos = forms.ChoiceField(choices=ATIVOS_CHOICES, required=False)

class ImportacaoExcelForm(forms.Form):
    arquivo = forms.FileField(label="Arquivo (.xlsx)")
    def clean_arquivo(self):
        f = self.cleaned_data["arquivo"]
        if not f.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Envie um arquivo .xlsx")
        return f
