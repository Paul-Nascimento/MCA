from django import forms

from .models import (
    Lancamento,
    Baixa,
    CategoriaFinanceira,
    TIPO_CHOICES,
    STATUS_CHOICES,
    FORMA_PGTO,
)

# Importes dos apps relacionados (sem executar queries aqui!)
from clientes.models import Cliente
from funcionarios.models import Funcionario
from condominios.models import Condominio
from turmas.models import Turma


class LancamentoForm(forms.ModelForm):
    class Meta:
        model = Lancamento
        fields = [
            "tipo",
            "descricao",
            "valor",
            "vencimento",
            "status",
            "cliente",
            "funcionario",
            "condominio",   # permanece no financeiro
            "turma",
            "categoria",
            "contraparte_nome",
            "contraparte_doc",
            "observacao",
            "ativo",
        ]
        widgets = {
            "vencimento": forms.DateInput(attrs={"type": "date"}),
            "observacao": forms.Textarea(attrs={"rows": 2}),
        }


class BaixaForm(forms.ModelForm):
    class Meta:
        model = Baixa
        fields = ["lancamento", "data", "valor", "forma", "observacao"]
        widgets = {"data": forms.DateInput(attrs={"type": "date"})}


class FiltroFinanceiroForm(forms.Form):
    q = forms.CharField(required=False, label="Busca")
    tipo = forms.ChoiceField(choices=(("", "Todos"),) + TIPO_CHOICES, required=False)
    status = forms.ChoiceField(choices=(("", "Todos"),) + STATUS_CHOICES, required=False)
    venc_de = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    venc_ate = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    # Evitar consultas na importação: começam como .none()
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.none(), required=False, empty_label="Todos"
    )
    funcionario = forms.ModelChoiceField(
        queryset=Funcionario.objects.none(), required=False, empty_label="Todos"
    )
    condominio = forms.ModelChoiceField(
        queryset=Condominio.objects.none(), required=False, empty_label="Todos"
    )
    turma = forms.ModelChoiceField(
        queryset=Turma.objects.none(), required=False, empty_label="Todas"
    )
    categoria = forms.ModelChoiceField(
        queryset=CategoriaFinanceira.objects.none(), required=False, empty_label="Todas"
    )

    ATIVOS_CHOICES = (("", "Todos"), ("1", "Ativos"), ("0", "Inativos"))
    ativos = forms.ChoiceField(choices=ATIVOS_CHOICES, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Agora é seguro popular os querysets (app registry pronto)
        self.fields["cliente"].queryset = Cliente.objects.all().order_by("nome_razao")
        self.fields["funcionario"].queryset = Funcionario.objects.filter(ativo=True).order_by("nome")
        self.fields["condominio"].queryset = Condominio.objects.all().order_by("nome")

        # Turma: mudou a ordenação — condomínio vem da modalidade
        self.fields["turma"].queryset = (
            Turma.objects
            .select_related("modalidade__condominio", "professor")
            .all()
            .order_by("modalidade__condominio__nome", "modalidade__nome", "hora_inicio", "id")
        )

        self.fields["categoria"].queryset = CategoriaFinanceira.objects.all().order_by("nome")


class RecorrenciaMensalForm(forms.Form):
    tipo = forms.ChoiceField(choices=TIPO_CHOICES)
    descricao = forms.CharField(max_length=255)
    valor = forms.DecimalField(min_value=0)
    dia_venc = forms.IntegerField(min_value=1, max_value=31, initial=5, label="Dia do vencimento")
    quantidade = forms.IntegerField(min_value=1, max_value=60, initial=12, label="Meses")
    primeiro_mes = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), label="Mês inicial (qualquer dia)")

    # Começam como .none(), populamos no __init__
    cliente = forms.ModelChoiceField(queryset=Cliente.objects.none(), required=False)
    funcionario = forms.ModelChoiceField(queryset=Funcionario.objects.none(), required=False)
    condominio = forms.ModelChoiceField(queryset=Condominio.objects.none(), required=False)
    turma = forms.ModelChoiceField(queryset=Turma.objects.none(), required=False)
    categoria = forms.ModelChoiceField(queryset=CategoriaFinanceira.objects.none(), required=False)

    observacao = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["cliente"].queryset = Cliente.objects.all().order_by("nome_razao")
        self.fields["funcionario"].queryset = Funcionario.objects.filter(ativo=True).order_by("nome")
        self.fields["condominio"].queryset = Condominio.objects.all().order_by("nome")

        # Turma: usar ordenação por modalidade/condomínio
        self.fields["turma"].queryset = (
            Turma.objects
            .select_related("modalidade__condominio", "professor")
            .all()
            .order_by("modalidade__condominio__nome", "modalidade__nome", "hora_inicio", "id")
        )

        self.fields["categoria"].queryset = CategoriaFinanceira.objects.all().order_by("nome")
