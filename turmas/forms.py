from django import forms
from .models import Turma, DIAS_SEMANA
from funcionarios.models import Funcionario
from modalidades.models import Modalidade
from condominios.models import Condominio
from clientes.models import Cliente

class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = [
            "professor", "modalidade", "condominio",
            "nome_exibicao", "valor", "capacidade",
            "dia_semana", "hora_inicio", "duracao_minutos",
            "inicio_vigencia", "fim_vigencia", "ativo",
        ]
        widgets = {
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "inicio_vigencia": forms.DateInput(attrs={"type": "date"}),
            "fim_vigencia": forms.DateInput(attrs={"type": "date"}),
        }

class TurmaFiltroForm(forms.Form):
    q = forms.CharField(label="Busca", required=False)
    condominio = forms.ModelChoiceField(
        queryset=Condominio.objects.all().order_by("nome"),
        required=False, empty_label="Todos"
    )
    modalidade = forms.ModelChoiceField(
        queryset=Modalidade.objects.all().order_by("nome"),
        required=False, empty_label="Todas"
    )
    professor = forms.ModelChoiceField(
        queryset=Funcionario.objects.filter(ativo=True).order_by("nome"),
        required=False, empty_label="Todos"
    )
    dia_semana = forms.ChoiceField(
        choices=[("", "Todos")] + [(k, v) for k, v in DIAS_SEMANA],
        required=False
    )
    ATIVOS_CHOICES = (("", "Todos"), ("1", "Ativas"), ("0", "Inativas"))
    ativos = forms.ChoiceField(choices=ATIVOS_CHOICES, required=False)

from django import forms
from clientes.models import Cliente

class MatriculaForm(forms.Form):
    turma_id = forms.IntegerField(widget=forms.HiddenInput())
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.none(),  # vazio na definição de classe
        required=True,
        label="Cliente (ativos)"
    )
    data_inicio = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ Use TODOS os clientes ativos para validar (sem [:500])
        qs = Cliente.objects.filter(ativo=True).order_by("nome_razao")

        # (Opcional, robusto) inclui explicitamente o ID postado se existir,
        # útil se o cliente ficou inativo após o render mas antes do POST.
        posted = self.data.get("cliente")
        if posted:
            try:
                qs = (qs | Cliente.objects.filter(pk=int(posted))).distinct()
            except (TypeError, ValueError):
                pass

        self.fields["cliente"].queryset = qs

# --- acrescente ao final de turmas/forms.py ---
from django import forms

class ListaPresencaCreateForm(forms.Form):
    turma_id = forms.IntegerField(widget=forms.HiddenInput())
    data = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), required=True)
    observacao_geral = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

class ListaPresencaRangeForm(forms.Form):
    turma_id = forms.IntegerField(widget=forms.HiddenInput())
    data_de = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), required=True, label="De")
    data_ate = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), required=True, label="Até")

class ListaFiltroForm(forms.Form):
    data_de = forms.DateField(widget=forms.DateInput(attrs={"type":"date"}), required=False, label="De")
    data_ate = forms.DateField(widget=forms.DateInput(attrs={"type":"date"}), required=False, label="Até")

