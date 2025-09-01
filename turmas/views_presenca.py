# turmas/views_presenca.py
from datetime import date
from typing import Dict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpRequest, HttpResponseBadRequest

from .models import Turma, ListaPresenca, ItemPresenca
from . import services_presenca as ps
from .forms import (
    ListaPresencaCreateForm,
    ListaPresencaRangeForm,
    ListaFiltroForm,
)

@login_required
def listas_da_turma(request: HttpRequest, turma_id: int):
    turma = (
        Turma.objects.select_related("modalidade", "condominio", "professor")
        .filter(id=turma_id)
        .first()
    )
    if not turma:
        messages.error(request, "Turma não encontrada.")
        return redirect(reverse("turmas:list"))

    filtro = ListaFiltroForm(request.GET or None)
    data_de = filtro.cleaned_data.get("data_de") if filtro.is_valid() else None
    data_ate = filtro.cleaned_data.get("data_ate") if filtro.is_valid() else None

    listas = ps.listas_da_turma(turma_id=turma.id, data_de=data_de, data_ate=data_ate)

    create_form = ListaPresencaCreateForm(initial={"turma_id": turma.id})
    auto_form = ListaPresencaRangeForm(initial={"turma_id": turma.id})

    return render(
        request,
        "turmas/presencas_list.html",
        {
            "turma": turma,
            "listas": listas,
            "filtro": filtro,
            "create_form": create_form,
            "auto_form": auto_form,
        },
    )

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

    try:
        lista = ps.criar_lista_presenca(turma_id=turma_id, d=d, observacao_geral=obs)
        messages.success(request, f"Lista de {d:%d/%m/%Y} criada.")
        return redirect(reverse("turmas:presenca_detalhe", args=[lista.id]))
    except ps.ListaJaExiste:
        messages.warning(request, "Já existe lista para essa data.")
    except Exception as e:
        messages.error(request, f"Não foi possível criar a lista: {e}")

    return redirect(reverse("turmas:presencas_turma", kwargs={"turma_id": int(turma_id)}))

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

    try:
        rel: Dict[str, int] = ps.gerar_listas_automaticas(
            turma_id=turma_id, data_de=d1, data_ate=d2
        )
        messages.success(
            request,
            f"Gerado: {rel['criadas']} nova(s). Já existiam: {rel['existentes']}. "
            f"Fora da vigência/dia: {rel['ignoradas_fora_vigencia']}.",
        )
    except Exception as e:
        messages.error(request, f"Falha na geração: {e}")

    return redirect(reverse("turmas:presencas_turma", kwargs={"turma_id": int(turma_id)}))

@login_required
def presenca_detalhe(request: HttpRequest, lista_id: int):
    try:
        lista, itens = ps.abrir_lista(lista_id)
    except Exception:
        lista, itens = None, None
    if not lista:
        messages.error(request, "Lista não encontrada.")
        return redirect(reverse("turmas:list"))

    return render(
        request,
        "turmas/presenca_detail.html",
        {
            "lista": lista,
            "itens": itens,
        },
    )

@login_required
def presenca_salvar_view(request: HttpRequest, lista_id: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    lista = ListaPresenca.objects.select_related("turma").filter(id=lista_id).first()
    if not lista:
        messages.error(request, "Lista não encontrada.")
        return redirect(reverse("turmas:list"))

    action = request.POST.get("action", "save")

    if action == "sync":
        try:
            rel = ps.sincronizar_itens_lista(lista.id)
            messages.success(
                request,
                f"Sincronizado. Adicionados: {rel['adicionados']}. Já existiam: {rel['existentes']}.",
            )
        except Exception as e:
            messages.error(request, f"Falha ao sincronizar: {e}")
        return redirect(reverse("turmas:presenca_detalhe", args=[lista.id]))

    if action == "mark_all":
        valor = request.POST.get("value", "1") == "1"
        updated = ItemPresenca.objects.filter(lista=lista).update(presente=valor)
        messages.success(
            request,
            f"{'Marcados' if valor else 'Desmarcados'} {updated} item(ns).",
        )
        return redirect(reverse("turmas:presenca_detalhe", args=[lista.id]))

    presentes_ids = {int(x) for x in request.POST.getlist("presentes")}
    obs_por_item = {}
    for key, val in request.POST.items():
        if key.startswith("obs_"):
            try:
                item_id = int(key.split("_", 1)[1])
                obs_por_item[item_id] = val
            except Exception:
                continue

    obs_geral = request.POST.get("observacao_geral", "") or ""

    try:
        ps.salvar_presenca(
            lista_id=lista.id,
            presentes_ids=presentes_ids,
            obs_por_item=obs_por_item,
            observacao_geral=obs_geral,
        )
        messages.success(request, "Lista salva com sucesso.")
    except Exception as e:
        messages.error(request, f"Falha ao salvar lista: {e}")

    return redirect(reverse("turmas:presenca_detalhe", args=[lista.id]))
