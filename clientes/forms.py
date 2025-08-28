from django import forms
from .models import Cliente

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            "cpf_cnpj", "nome_razao", "data_nascimento",
            "telefone_emergencial", "telefone_celular", "email",
            "cep", "numero_id", "logradouro", "bairro", "complemento",
            "municipio", "estado", "ativo",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
            "ativo": forms.CheckboxInput(),
        }

class ClienteFiltroForm(forms.Form):
    q = forms.CharField(label="Busca", required=False)
    ATIVOS_CHOICES = (
        ("", "Todos"),
        ("1", "Ativos"),
        ("0", "Inativos"),
    )
    ativos = forms.ChoiceField(choices=ATIVOS_CHOICES, required=False)

class ImportacaoExcelForm(forms.Form):
    arquivo = forms.FileField(label="Arquivo (.xlsx)")

    def clean_arquivo(self):
        f = self.cleaned_data["arquivo"]
        if not f.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Envie um arquivo .xlsx")
        return f
