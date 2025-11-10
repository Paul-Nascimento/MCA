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
            "nome_exibicao",

            # 💰 Valores financeiros
            "valor",
            "valor_dsr",
            "vale_transporte",
            "bonificacao",

            "capacidade",
            "hora_inicio",
            "duracao_minutos",

            # 🗓️ Dias de semana
            "seg", "ter", "qua", "qui", "sex", "sab", "dom",

            # 📆 Vigência
            "inicio_vigencia",
            "fim_vigencia",

            # 📝 Observações
            "observacoes",

            "ativo",
        ]

        widgets = {
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "inicio_vigencia": forms.DateInput(attrs={"type": "date"}),
            "fim_vigencia": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()

        # ✅ Verifica se pelo menos 1 dia da semana foi selecionado
        dias = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
        if not any(cleaned_data.get(d) for d in dias):
            raise ValidationError("Selecione ao menos um dia da semana.")

        # ✅ Checa vigência
        ini = cleaned_data.get("inicio_vigencia")
        fim = cleaned_data.get("fim_vigencia")
        if ini and fim and fim < ini:
            raise ValidationError("A data de fim da vigência não pode ser anterior ao início.")

        return cleaned_data


class TurmaFiltroForm(forms.Form):
    q = forms.CharField(required=False, label="Buscar")
    condominio = forms.IntegerField(required=False)
    modalidade = forms.IntegerField(required=False)
    professor = forms.IntegerField(required=False)

    DIA_CHOICES = [("", "Todos")] + [
        ("0", "Seg"), ("1", "Ter"), ("2", "Qua"), ("3", "Qui"),
        ("4", "Sex"), ("5", "Sáb"), ("6", "Dom")
    ]

    dia_semana = forms.ChoiceField(required=False, choices=DIA_CHOICES, label="Dia da Semana")

    ativos = forms.ChoiceField(
        required=False,
        choices=(("", "Todos"), ("1", "Ativas"), ("0", "Inativas")),
        label="Status"
    )

class MatriculaForm(forms.Form):
    turma_id = forms.IntegerField()
    cliente = forms.IntegerField()
    data_inicio = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    participante_nome = forms.CharField(required=False)

    # ✅ Alterado: CPF -> Data de nascimento
    participante_data_nascimento = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Data de Nascimento do Participante"
    )

    participante_idade = forms.IntegerField(required=False, min_value=0)

    participante_sexo = forms.ChoiceField(
        required=False,
        choices=(("", "--"), ("M", "M"), ("F", "F"), ("O", "Outro"))
    )

    def clean(self):
        cleaned_data = super().clean()

        # Se preencher nome, mas não data de nascimento, tudo bem (participante pode ser menor sem data)
        # Se nenhum dos campos for preenchido -> é o próprio cliente
        participante_nome = cleaned_data.get("participante_nome")
        data_nasc = cleaned_data.get("participante_data_nascimento")

        if participante_nome and not data_nasc:
            # Apenas alerta — se quiser tornar obrigatório, descomente a validação abaixo
            # raise forms.ValidationError("Se informar participante, precisa da data de nascimento.")
            pass

        return cleaned_data



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
