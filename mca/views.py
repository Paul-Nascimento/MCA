# mca/views.py
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum, F, Value as V, DecimalField, Count
from django.db.models.functions import Coalesce

from financeiro.models import Lancamento   # tipo: "RECEBER"/"PAGAR", valor, status, relação com baixas
from turmas.models import Turma, Matricula # Matricula(ativa=True), Turma(valor|preco, capacidade|limite_vagas)

def _sum_saldo(qs):
    """
    Soma do saldo (valor - baixas) item a item, evitando overcount de JOIN.
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

    print('Aq')
    total_receber = _sum_saldo(base.filter(tipo="RECEBER"))
    total_pagar   = _sum_saldo(base.filter(tipo="PAGAR"))

    print(f'Total a receber {total_receber}')

    # --- Faturamento previsto (matrículas ativas x valor/preço da turma) ---
    valor_field = _detect_field(Turma, ["valor", "preco"])
    faturamento_previsto = Decimal('0')
    if valor_field:
        faturamento_previsto = (
            Matricula.objects.filter(ativa=True)
            .aggregate(total=Coalesce(Sum(F(f"turma__{valor_field}")), V(0), output_field=DecimalField(max_digits=14, decimal_places=2)))
            .get("total") or Decimal('0')
        )

    # --- Ocupação das turmas ---
    cap_field = _detect_field(Turma, ["capacidade", "limite_vagas"])
    ocupacao_percentual = None
    if cap_field:
        # capacidade total
        cap_total = (
            Turma.objects.aggregate(
                total_cap=Coalesce(Sum(F(cap_field)), V(0), output_field=DecimalField(max_digits=14, decimal_places=2))
            ).get("total_cap") or 0
        )
        # matrículas ativas
        matriculas_ativas = Matricula.objects.filter(ativa=True).count()
        if cap_total and cap_total > 0:
            ocupacao_percentual = (Decimal(matriculas_ativas) / Decimal(cap_total)) * Decimal('100')
        else:
            ocupacao_percentual = Decimal('0')

    ctx = {
        "total_receber": total_receber,
        "total_pagar": total_pagar,
        "faturamento_previsto": faturamento_previsto,
        "ocupacao_percentual": None if ocupacao_percentual is None else ocupacao_percentual.quantize(Decimal('0.01')),
    }
    return render(request, "home.html", ctx)
