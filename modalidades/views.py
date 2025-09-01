from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse

from .forms import ModalidadeForm, ModalidadeFiltroForm
from . import services as cs

@login_required
def list_modalidades(request: HttpRequest):
    q = request.GET.get("q", "").strip()
    ativos_param = request.GET.get("ativos", "")
    if   ativos_param == "1": ativos = True
    elif ativos_param == "0": ativos = False
    else:                     ativos = None

    qs = cs.buscar_modalidades(q=q, ativos=ativos)

    page_str = request.GET.get("page", "1")
    try:
        page = int(page_str)
        if page < 1: page = 1
    except (TypeError, ValueError):
        page = 1

    page_obj = cs.paginar_queryset(qs, page=page, per_page=20)

    qd = request.GET.copy()
    qd.pop("page", None)
    base_qs = qd.urlencode()
    suffix = f"&{base_qs}" if base_qs else ""

    filtro_form = ModalidadeFiltroForm(initial={"q": q, "ativos": ativos_param})
    form = ModalidadeForm()

    return render(request, "modalidades/list.html", {
        "page_obj": page_obj,
        "filtro_form": filtro_form,
        "form": form,
        "q": q, "ativos_param": ativos_param,
        "base_qs": base_qs, "suffix": suffix,
    })

@login_required
def create_modalidade(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = ModalidadeForm(request.POST)
    if form.is_valid():
        try:
            cs.criar_modalidade(form.cleaned_data)
            messages.success(request, "Modalidade criada com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao criar: {e}")
    else:
        messages.error(request, "Dados inválidos.")
    return redirect(reverse("modalidades:list"))

@login_required
def update_modalidade(request: HttpRequest, pk: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = ModalidadeForm(request.POST)
    if form.is_valid():
        try:
            cs.atualizar_modalidade(pk, form.cleaned_data)
            messages.success(request, "Modalidade atualizada com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao atualizar: {e}")
    else:
        messages.error(request, "Dados inválidos.")
    return redirect(reverse("modalidades:list"))
