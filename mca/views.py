# mca/views.py
from __future__ import annotations
from datetime import date, timedelta
from typing import List, Dict

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth, Coalesce
from django.shortcuts import render
from django.utils import timezone

from financeiro.models import Lancamento
from turmas.models import Turma, Matricula


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)

@login_required
def home(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    # últimos 6 meses (inclui o mês atual)
    months: List[date] = [_add_months(month_start, i - 5) for i in range(6)]
    month_labels = [f"{m.month:02d}/{m.year}" for m in months]

    # ====== Financeiro: receivíveis ======
    # heurísticas para compatibilizar nomes diferentes nos seus models:
    q_receber = Q(tipo="RECEBER") | Q(natureza="RECEBER") | Q(eh_receber=True)
    q_liquidado = Q(status="LIQUIDADO")
    q_cancelado = Q(status="CANCELADO")
    q_aberto = ~q_liquidado & ~q_cancelado

    qs_rec = Lancamento.objects.filter(q_receber)

    # KPIs
    total_aberto = qs_rec.filter(q_aberto).aggregate(x=Coalesce(Sum("valor"), 0))["x"]
    total_atrasado = qs_rec.filter(q_aberto, vencimento__lt=today).aggregate(x=Coalesce(Sum("valor"), 0))["x"]
    recebido_mes = qs_rec.filter(q_liquidado, vencimento__gte=month_start, vencimento__lt=_add_months(month_start, 1)).aggregate(x=Coalesce(Sum("valor"), 0))["x"]

    # Séries por mês (baseadas no vencimento)
    base_6m = qs_rec.filter(vencimento__gte=months[0], vencimento__lt=_add_months(months[-1], 1))
    por_mes = (
        base_6m
        .annotate(m=TruncMonth("vencimento"))
        .values("m")
        .annotate(
            previsto=Coalesce(Sum("valor"), 0),
            recebido=Coalesce(Sum("valor", filter=q_liquidado), 0),
            aberto=Coalesce(Sum("valor", filter=q_aberto), 0),
        )
    )
    idx = {r["m"].date(): r for r in por_mes}
    serie_previsto = [float(idx.get(m, {}).get("previsto", 0) or 0) for m in months]
    serie_recebido = [float(idx.get(m, {}).get("recebido", 0) or 0) for m in months]
    serie_aberto = [float(idx.get(m, {}).get("aberto", 0) or 0) for m in months]

    # ====== Turmas: ocupação e próximas aulas ======
    turmas_qs = (
        Turma.objects.select_related("modalidade", "condominio", "professor")
        .filter(ativo=True)
        .annotate(ocupacao_qtd=Count("matriculas", filter=Q(matriculas__ativa=True)))
    )

    # Top 8 por taxa de ocupação
    turmas_data = []
    for t in turmas_qs:
        cap = t.capacidade or 0
        occ = getattr(t, "ocupacao_qtd", 0)
        taxa = (occ / cap * 100.0) if cap else 0.0
        turmas_data.append((t, occ, cap, taxa))
    turmas_data.sort(key=lambda x: x[3], reverse=True)
    top = turmas_data[:8]
    chart_turmas_labels = [f"{t.modalidade.nome} - {t.condominio.nome}"[:28] for (t, *_rest) in top]
    chart_turmas_occ = [int(occ) for (_t, occ, _cap, _tx) in top]
    chart_turmas_cap = [int(cap) for (_t, _occ, cap, _tx) in top]

    # Próximas aulas (próximos 7 dias)
    def prox_data_da_turma(t: Turma, ref: date) -> date:
        delta = (t.dia_semana - ref.weekday()) % 7
        return ref + timedelta(days=delta)

    ate = today + timedelta(days=7)
    proximas = []
    for t, occ, cap, _tx in turmas_data[:50]:  # limita por performance
        dnext = prox_data_da_turma(t, today)
        if dnext <= ate:
            proximas.append({
                "data": dnext,
                "hora": t.hora_inicio,
                "titulo": t.nome_exibicao or t.modalidade.nome,
                "condominio": t.condominio.nome,
                "professor": t.professor.nome,
                "ocupacao": occ,
                "capacidade": cap,
                "turma_id": t.id,
            })
    proximas.sort(key=lambda x: (x["data"], x["hora"]))

    context = {
        # KPIs
        "kpi_total_aberto": total_aberto,
        "kpi_total_atrasado": total_atrasado,
        "kpi_recebido_mes": recebido_mes,
        "kpi_turmas_ativas": turmas_qs.count(),
        "kpi_matriculas_ativas": Matricula.objects.filter(ativa=True).count(),

        # Charts (series)
        "month_labels": month_labels,
        "serie_previsto": serie_previsto,
        "serie_recebido": serie_recebido,
        "serie_aberto": serie_aberto,

        "chart_turmas_labels": chart_turmas_labels,
        "chart_turmas_occ": chart_turmas_occ,
        "chart_turmas_cap": chart_turmas_cap,

        # Lista
        "proximas": proximas,
        "today": today,
    }
    return render(request, "home.html", context)
