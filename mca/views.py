# mca/views.py
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum, F, Value as V, DecimalField
from django.db.models.functions import Coalesce

from financeiro.models import Lancamento
from turmas.models import Turma, Matricula

def _sum_saldo(qs):
    """
    Soma do saldo (valor - baixas) item a item, evitando overcount de JOIN.
    Considera apenas valores positivos (o que ainda falta receber/pagar).
    """
    rows = qs.annotate(
        pago=Coalesce(Sum('baixas__valor'), V(0), output_field=DecimalField(max_digits=14, decimal_places=2))
    ).values('valor', 'pago')
    total = Decimal('0')
    for r in rows:
        val = (r['valor'] or Decimal('0')) - (r['pago'] or Decimal('0'))
        if val > 0:
            total += val
    return total

def _detect_field(model, candidates):
    names = {f.name for f in model._meta.get_fields()}
    for c in candidates:
        if c in names:
            return c
    return None

@login_required
def home(request):
    # --- Financeiro: totais de saldo (exclui CANCELADO) ---
    base = Lancamento.objects.exclude(status="CANCELADO")

    total_receber = _sum_saldo(base.filter(tipo="RECEBER"))
    total_pagar   = _sum_saldo(base.filter(tipo="PAGAR"))

    # --- Faturamento previsto (matrículas ativas x valor/preço da turma) ---
    faturamento_previsto = Decimal('0')
    valor_field = _detect_field(Turma, ["valor", "preco"])
    if valor_field:
        faturamento_previsto = (
            Matricula.objects.filter(ativa=True)
            .aggregate(total=Coalesce(Sum(F(f"turma__{valor_field}")), V(0), output_field=DecimalField(max_digits=14, decimal_places=2)))
            .get("total") or Decimal('0')
        )

    # --- Ocupação das turmas ---
    ocupacao_percentual = Decimal('0')
    cap_field = _detect_field(Turma, ["capacidade", "limite_vagas"])
    if cap_field:
        cap_total = (
            Turma.objects.aggregate(
                total_cap=Coalesce(Sum(F(cap_field)), V(0), output_field=DecimalField(max_digits=14, decimal_places=2))
            ).get("total_cap") or Decimal('0')
        )
        matriculas_ativas = Matricula.objects.filter(ativa=True).count()
        if cap_total and Decimal(cap_total) > 0:
            ocupacao_percentual = (Decimal(matriculas_ativas) / Decimal(cap_total)) * Decimal('100')

    # --- Listas rápidas para o dashboard (opcional) ---
    proximos_receber = (
        base.filter(tipo="RECEBER")
            .order_by("vencimento", "id")[:8]
            .select_related("cliente", "categoria")
    )
    proximos_pagar = (
    base.filter(tipo="PAGAR")
        .order_by("vencimento", "id")[:8]
        .select_related("cliente", "funcionario", "condominio", "turma", "categoria")
)


    ctx = {
        "total_receber": total_receber,
        "total_pagar": total_pagar,
        "faturamento_previsto": faturamento_previsto,
        "ocupacao_percentual": ocupacao_percentual.quantize(Decimal('0.01')),
        "proximos_receber": proximos_receber,
        "proximos_pagar": proximos_pagar,
    }
    return render(request, "home.html", ctx)
