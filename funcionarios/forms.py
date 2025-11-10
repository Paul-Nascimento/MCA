from django import forms
from .models import Funcionario


class FuncionarioForm(forms.ModelForm):
    class Meta:
        model = Funcionario
        fields = [
            "cpf_cnpj",
            "nome",
            "email",
            "telefone",
            "rg",                # ✅ novo
            "registro_cref",     # ✅ novo
            "tam_uniforme",      # ✅ novo
            "data_nascimento",
            "data_admissao",     # ✅ novo
            "cargo",
            "regime_trabalhista",
            "ativo",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_admissao": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "cargo": forms.Select(choices=Funcionario.Cargo.choices),
            "regime_trabalhista": forms.Select(choices=Funcionario.RegimeTrabalhista.choices),
        }

    def clean(self):
        cleaned_data = super().clean()
        cargo = cleaned_data.get("cargo")
        registro_cref = cleaned_data.get("registro_cref")

        # ✅ Validação: se for professor, CREF é obrigatório
        if cargo == Funcionario.Cargo.PROFESSOR and not registro_cref:
            self.add_error("registro_cref", "Registro CREF é obrigatório para professores.")

        return cleaned_data


class FuncionarioFiltroForm(forms.Form):
    q = forms.CharField(label="Busca (nome, e-mail, CPF/CNPJ)", required=False)

    ATIVOS_CHOICES = (("", "Todos"), ("1", "Ativos"), ("0", "Inativos"))
    ativos = forms.ChoiceField(choices=ATIVOS_CHOICES, required=False, label="Status")

    cargo = forms.ChoiceField(
        choices=[("", "Todos")] + list(Funcionario.Cargo.choices),
        required=False,
        label="Cargo",
    )


class ImportacaoExcelForm(forms.Form):
    arquivo = forms.FileField(label="Arquivo (.xlsx)")

    def clean_arquivo(self):
        f = self.cleaned_data["arquivo"]
        if not f.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Envie um arquivo .xlsx válido")
        return f
