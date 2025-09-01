# turmas/forms.py
from __future__ import annotations
from django import forms
from .models import Turma

class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = [
            "professor", "modalidade", "condominio", "nome_exibicao",
            "valor", "capacidade", "dia_semana", "hora_inicio",
            "duracao_minutos", "inicio_vigencia", "fim_vigencia", "ativo"
        ]
        widgets = {
            "hora_inicio": forms.TimeInput(attrs={"type":"time"}),
            "inicio_vigencia": forms.DateInput(attrs={"type":"date"}),
            "fim_vigencia": forms.DateInput(attrs={"type":"date"}),
        }

class TurmaFiltroForm(forms.Form):
    q = forms.CharField(required=False)
    condominio = forms.IntegerField(required=False)
    modalidade = forms.IntegerField(required=False)
    professor = forms.IntegerField(required=False)
    dia_semana = forms.ChoiceField(required=False, choices=[("","Todos")]+[(i, Turma.DIAS_SEMANA[i][1] if hasattr(Turma, "DIAS_SEMANA") else str(i)) for i in range(0,7)])
    ativos = forms.ChoiceField(required=False, choices=(("","Todos"),("1","Ativas"),("0","Inativas")))

class MatriculaForm(forms.Form):
    turma_id = forms.IntegerField()
    cliente = forms.IntegerField()
    data_inicio = forms.DateField(widget=forms.DateInput(attrs={"type":"date"}))
    participante_nome = forms.CharField(required=False)
    participante_cpf = forms.CharField(required=False)
    participante_sexo = forms.ChoiceField(required=False, choices=(("","--"),("M","M"),("F","F"),("O","Outro")))

# ---- Presenças ----
class ListaPresencaCreateForm(forms.Form):
    turma_id = forms.IntegerField()
    data = forms.DateField(widget=forms.DateInput(attrs={"type":"date"}))
    observacao_geral = forms.CharField(required=False)

class ListaPresencaRangeForm(forms.Form):
    turma_id = forms.IntegerField()
    data_de = forms.DateField(widget=forms.DateInput(attrs={"type":"date"}))
    data_ate = forms.DateField(widget=forms.DateInput(attrs={"type":"date"}))

class ListaFiltroForm(forms.Form):
    data_de = forms.DateField(required=False, widget=forms.DateInput(attrs={"type":"date"}))
    data_ate = forms.DateField(required=False, widget=forms.DateInput(attrs={"type":"date"}))
