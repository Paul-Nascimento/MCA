from __future__ import annotations
from typing import Dict, Set
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.timezone import localdate

from .models import Turma, ListaPresenca, ItemPresenca, Matricula
from .forms import (
    ListaPresencaCreateForm,
    ListaPresencaRangeForm,
    ListaFiltroForm,
)
# Se você tem services específicos de presença, pode importar aqui:
# from . import services_presenca as ps


# ----------------- Helpers -----------------

def _matriculas_ativas_na_data(lista: ListaPresenca):
    """
    Matrículas ativas na data da lista e pertencentes à turma.
    Ativa = (ativa=True) AND data_inicio <= data <= (data_fim or +inf).
    """
    d = lista.data
    return (
        Matricula.objects
        .select_related("cliente", "turma")
        .filter(
            turma=lista.turma,
            ativa=True
        )
        .filter(Q(data_fim__isnull=True) | Q(data_fim__gte=d))
        .order_by("cliente__nome_razao", "id")
    )


def _snapshots_from_matricula(m: Matricula) -> tuple[str, str]:
    """
    Nome/doc do aluno no dia: usa participante (se houver) senão cliente.
    """
    nome = (m.participante_nome or m.cliente.nome_razao or "").strip()
    doc = (m.participante_cpf or m.cliente.cpf_cnpj or "").strip()
    return nome, doc


# ----------------- Listagem de listas da turma -----------------
from django.db.models import Count, Sum, Case, When, IntegerField

@login_required
def listas_da_turma(request: HttpRequest, turma_id: int):
    turma = (
        Turma.objects.select_related("modalidade",  "professor")
        .filter(id=turma_id)
        .first()
    )
    if not turma:
        messages.error(request, "Turma não encontrada.")
        return redirect(reverse("turmas:list"))

    filtro = ListaFiltroForm(request.GET or None)
    data_de = filtro.cleaned_data.get("data_de") if filtro.is_valid() else None
    data_ate = filtro.cleaned_data.get("data_ate") if filtro.is_valid() else None

    qs = (
        ListaPresenca.objects
        .filter(turma=turma)
        .annotate(
            # total de linhas na lista
            total_itens_count=Count("itens", distinct=True),
            # total de presentes marcados (somando 1 quando presente=True)
            total_presentes_count=Sum(
                Case(
                    When(itens__presente=True, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
        )
        .order_by("-data", "-id")
    )

    if data_de:
        qs = qs.filter(data__gte=data_de)
    if data_ate:
        qs = qs.filter(data__lte=data_ate)

    # cria automaticamente a de hoje se não houver nenhuma (opcional)
    if not data_de and not data_ate and not qs.exists():
        hoje = localdate()
        lista, created = ListaPresenca.objects.get_or_create(turma=turma, data=hoje)
        if created:
            messages.info(request, f"Lista de presença criada para hoje ({hoje:%d/%m/%Y}).")
        qs = (
            ListaPresenca.objects.filter(turma=turma)
            .annotate(
                total_itens_count=Count("itens", distinct=True),
                total_presentes_count=Sum(
                    Case(
                        When(itens__presente=True, then=1),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
            )
            .order_by("-data", "-id")
        )

    create_form = ListaPresencaCreateForm(initial={"turma_id": turma.id})
    auto_form = ListaPresencaRangeForm(initial={"turma_id": turma.id})

    return render(
        request,
        "turmas/presencas_list.html",
        {
            "turma": turma,
            "listas": qs,
            "filtro": filtro,
            "create_form": create_form,
            "auto_form": auto_form,
        },
    )



# ----------------- Criar listas -----------------

@login_required
def criar_lista_presenca_view(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = ListaPresencaCreateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Dados inválidos para criar lista.")
        return redirect(reverse("turmas:list"))

    turma_id = form.cleaned_data["turma_id"]
    d = form.cleaned_data["data"]
    obs = form.cleaned_data.get("observacao_geral", "") or ""

    turma = get_object_or_404(Turma, id=turma_id)
    lista, created = ListaPresenca.objects.get_or_create(turma=turma, data=d)
    if created:
        lista.observacao_geral = obs
        lista.save(update_fields=["observacao_geral"])
        messages.success(request, f"Lista de {d:%d/%m/%Y} criada.")
    else:
        messages.warning(request, "Já existe lista para essa data.")
    return redirect(reverse("turmas:presenca_detalhe", args=[lista.id]))


@login_required
def gerar_listas_automaticas_view(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = ListaPresencaRangeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Período inválido para geração automática.")
        return redirect(reverse("turmas:list"))

    turma_id = form.cleaned_data["turma_id"]
    d1 = form.cleaned_data["data_de"]
    d2 = form.cleaned_data["data_ate"]

    turma = get_object_or_404(Turma, id=turma_id)

    # Geração simples por intervalo respeitando dias ativos e vigência
    from datetime import timedelta
    criadas = 0
    existentes = 0
    ignoradas = 0

    cur = d1
    while cur <= d2:
        # validar vigência e dia ativo
        if cur < turma.inicio_vigencia or (turma.fim_vigencia and cur > turma.fim_vigencia):
            ignoradas += 1
        elif cur.weekday() not in turma.dias_ativos():
            ignoradas += 1
        else:
            _, created = ListaPresenca.objects.get_or_create(turma=turma, data=cur)
            if created:
                criadas += 1
            else:
                existentes += 1
        cur += timedelta(days=1)

    messages.success(
        request,
        f"Gerado: {criadas} nova(s). Já existiam: {existentes}. Ignoradas: {ignoradas}."
    )
    return redirect(reverse("turmas:presencas_turma", args=[turma.id]))


# ----------------- Tela baseada em MATRÍCULA -----------------

from . import services_presenca as ps

@login_required
def presenca_detalhe(request: HttpRequest, lista_id: int):
    lista, itens = ps.abrir_lista(lista_id)  # itens = QuerySet[ItemPresenca]
    presente_ids = {it.id for it in itens if it.presente}
    obs_por_item = {it.id: (it.observacao or "") for it in itens}
    return render(
        request,
        "turmas/presenca_detail.html",
        {
            "lista": lista,
            "itens": itens,                 # <<< iterar por itens (cada linha é 1 ItemPresenca)
            "presente_ids": presente_ids,   # <<< checkboxes por item.id
            "obs_por_item": obs_por_item,
        },
    )



# ----------------- Salvar checkboxes -----------------
@login_required
@transaction.atomic
def presenca_salvar_view(request: HttpRequest, lista_id: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")

    presentes_ids = [int(x) for x in request.POST.getlist("presentes")]  # lista de item.id

    obs_por_item = {}
    for k, v in request.POST.items():
        if k.startswith("obs_I"):  # no template, use name="obs_I{{ item.id }}"
            try:
                iid = int(k[5:])
                obs_por_item[iid] = (v or "").strip()
            except Exception:
                pass

    obs_geral = (request.POST.get("observacao_geral") or "").strip()

    ps.salvar_presenca(
        lista_id=lista_id,
        presentes_ids=presentes_ids,
        obs_por_item=obs_por_item,
        observacao_geral=obs_geral,
    )
    messages.success(request, "Lista salva.")
    return redirect(reverse("turmas:presenca_detalhe", args=[lista_id]))
