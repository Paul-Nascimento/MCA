from __future__ import annotations
from django import forms
from django.core.exceptions import ValidationError

from .models import Turma, DIAS_SEMANA

class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = [
            "professor",
            "modalidade",
            # "condominio",  # <- REMOVER
            "nome_exibicao",
            "valor",
            "capacidade",
            "hora_inicio",
            "duracao_minutos",
            "seg","ter","qua","qui","sex","sab","dom",
            "inicio_vigencia",
            "fim_vigencia",
            "ativo",
        ]
        # widgets inalterados

    def clean(self):
        cd = super().clean()
        # Pelo menos um dia marcado
        dias = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
        if not any(bool(cd.get(d)) for d in dias):
            raise ValidationError("Selecione ao menos um dia da semana.")
        # Vigência coerente
        ini = cd.get("inicio_vigencia")
        fim = cd.get("fim_vigencia")
        if ini and fim and fim < ini:
            raise ValidationError("A data de fim da vigência não pode ser anterior ao início.")
        return cd


class TurmaFiltroForm(forms.Form):
    q = forms.CharField(required=False)
    condominio = forms.IntegerField(required=False)
    modalidade = forms.IntegerField(required=False)
    professor = forms.IntegerField(required=False)

    DIA_CHOICES = [("", "Todos")] + [(str(i), label) for i, label in DIAS_SEMANA]
    dia_semana = forms.ChoiceField(required=False, choices=DIA_CHOICES)

    ativos = forms.ChoiceField(
        required=False, choices=(("", "Todos"), ("1", "Ativas"), ("0", "Inativas"))
    )


class MatriculaForm(forms.Form):
    turma_id = forms.IntegerField()
    cliente = forms.IntegerField()
    data_inicio = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    participante_nome = forms.CharField(required=False)
    participante_cpf = forms.CharField(required=False)
    participante_idade = forms.IntegerField(required=False, min_value=0)
    participante_sexo = forms.ChoiceField(
        required=False, choices=(("", "--"), ("M", "M"), ("F", "F"), ("O", "Outro"))
    )

    def clean_participante_cpf(self):
        import re
        raw = self.cleaned_data.get("participante_cpf") or ""
        only_digits = re.sub(r"\D+", "", raw)
        return only_digits


# ---- Presenças ----
class ListaPresencaCreateForm(forms.Form):
    turma_id = forms.IntegerField()
    data = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    observacao_geral = forms.CharField(required=False)


class ListaPresencaRangeForm(forms.Form):
    turma_id = forms.IntegerField()
    data_de = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    data_ate = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cd = super().clean()
        d1, d2 = cd.get("data_de"), cd.get("data_ate")
        if d1 and d2 and d2 < d1:
            raise ValidationError("O período é inválido: data final anterior à inicial.")
        return cd


class ListaFiltroForm(forms.Form):
    data_de = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    data_ate = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cd = super().clean()
        d1, d2 = cd.get("data_de"), cd.get("data_ate")
        if d1 and d2 and d2 < d1:
            raise ValidationError("O período do filtro é inválido: data final anterior à inicial.")
        return cd
