# turmas/views.py
from __future__ import annotations
from typing import Optional
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Turma
from . import services as ts
from .forms import TurmaForm, TurmaFiltroForm, MatriculaForm

from clientes.models import Cliente
from condominios.models import Condominio
from modalidades.models import Modalidade
from funcionarios.models import Funcionario  # professor

# ============== Helpers ==============

def _paginate(qs, page: int, per_page: int = 20):
    p = Paginator(qs, per_page)
    try:
        return p.page(page)
    except PageNotAnInteger:
        return p.page(1)
    except EmptyPage:
        return p.page(p.num_pages if page > 1 else 1)

# ============== Views ==============

@login_required
def list_turmas(request: HttpRequest):
    # filtros
    filtro = TurmaFiltroForm(request.GET or None)
    cd = filtro.cleaned_data if filtro.is_valid() else {}

    q = cd.get("q", "")
    condominio_id = int(cd["condominio"]) if cd.get("condominio") else None
    modalidade_id = int(cd["modalidade"]) if cd.get("modalidade") else None
    professor_id = int(cd["professor"]) if cd.get("professor") else None
    dia_semana = cd.get("dia_semana")
    ativos = None if cd.get("ativos") in ("", None) else (cd.get("ativos") == "1")

    qs = ts.buscar_turmas(
        q=q,
        condominio_id=condominio_id,
        modalidade_id=modalidade_id,
        professor_id=professor_id,
        dia_semana=dia_semana if dia_semana != "" else None,
        ativos=ativos,
    )

    # paginação
    page_str = request.GET.get("page", "1")
    try:
        page = max(1, int(page_str))
    except Exception:
        page = 1
    page_obj = _paginate(qs, page=page, per_page=20)

    # parâmetros auxiliares para template
    qd = request.GET.copy(); qd.pop("page", None)
    base_qs = qd.urlencode()
    suffix = f"&{base_qs}" if base_qs else ""

    # combos
    condominios = Condominio.objects.order_by("nome")
    modalidades = Modalidade.objects.order_by("nome")
    professores = Funcionario.objects.filter(ativo=True, cargo__icontains="prof").order_by("nome") if hasattr(Funcionario, "cargo") else Funcionario.objects.filter(ativo=True).order_by("nome")
    # clientes (para o modal de matrícula) - limitar por performance
    clientes = Cliente.objects.filter(ativo=True).order_by("nome_razao")[:500]

    context = {
        "filtro_form": filtro,
        "page_obj": page_obj,
        "base_qs": base_qs,
        "suffix": suffix,
        "condominios": condominios,
        "modalidades": modalidades,
        "professores": professores,
        "clientes": clientes,
        "DIAS_SEMANA": Turma.DIAS_SEMANA if hasattr(Turma, "DIAS_SEMANA") else [(0,"Seg"),(1,"Ter"),(2,"Qua"),(3,"Qui"),(4,"Sex"),(5,"Sáb"),(6,"Dom")],
        # usados no template para manter 'selected'
        "condominio_id": request.GET.get("condominio",""),
        "modalidade_id": request.GET.get("modalidade",""),
        "professor_id": request.GET.get("professor",""),
        "dia_param": request.GET.get("dia_semana",""),
        "ativos_param": request.GET.get("ativos",""),
    }
    return render(request, "turmas/list.html", context)

@login_required
def create_turma(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = TurmaForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Dados inválidos: {form.errors}")
        return redirect(reverse("turmas:list"))
    try:
        ts.criar_turma(form.cleaned_data)
        messages.success(request, "Turma criada.")
    except Exception as e:
        messages.error(request, f"Erro ao criar turma: {e}")
    return redirect(reverse("turmas:list"))

@login_required
def update_turma(request: HttpRequest, pk: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = TurmaForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Dados inválidos: {form.errors}")
        return redirect(reverse("turmas:list"))
    try:
        ts.atualizar_turma(pk, form.cleaned_data)
        messages.success(request, "Turma atualizada.")
    except Exception as e:
        messages.error(request, f"Erro ao atualizar turma: {e}")
    return redirect(reverse("turmas:list"))

@login_required
def alunos_turma(request: HttpRequest, turma_id: int):
    turma = Turma.objects.select_related("modalidade","condominio","professor").filter(id=turma_id).first()
    if not turma:
        messages.error(request, "Turma não encontrada.")
        return redirect(reverse("turmas:list"))
    alunos = ts.alunos_da_turma(turma_id)
    return render(request, "turmas/alunos.html", {"turma": turma, "alunos": alunos})

@login_required
def matricular_view(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = MatriculaForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Dados inválidos: {form.errors}")
        return redirect(reverse("turmas:list"))

    cd = form.cleaned_data
    try:
        ts.matricular_cliente(
            turma_id=cd["turma_id"],
            cliente_id=cd["cliente"],
            data_inicio=cd["data_inicio"],
            participante_nome=cd.get("participante_nome",""),
            participante_cpf=cd.get("participante_cpf",""),
            participante_sexo=cd.get("participante_sexo",""),
        )
        messages.success(request, "Matrícula realizada.")
    except Exception as e:
        messages.error(request, f"Falha ao matricular: {e}")
    return redirect(reverse("turmas:list"))

@login_required
def exportar_view(request: HttpRequest):
    qs = ts.buscar_turmas(
        q=request.GET.get("q",""),
        condominio_id=int(request.GET.get("condominio")) if request.GET.get("condominio") else None,
        modalidade_id=int(request.GET.get("modalidade")) if request.GET.get("modalidade") else None,
        professor_id=int(request.GET.get("professor")) if request.GET.get("professor") else None,
        dia_semana=int(request.GET.get("dia_semana")) if request.GET.get("dia_semana","") != "" else None,
        ativos=(None if request.GET.get("ativos","") == "" else request.GET.get("ativos")=="1"),
    )
    filename, content = ts.exportar_turmas_excel(qs)
    resp = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


# turmas/views.py (substitua/atualize estas duas views)

from django.utils.timezone import now

@login_required
def alunos_turma(request: HttpRequest, turma_id: int):
    turma = Turma.objects.select_related("modalidade","condominio","professor").filter(id=turma_id).first()
    if not turma:
        messages.error(request, "Turma não encontrada.")
        return redirect(reverse("turmas:list"))

    qs = ts.alunos_da_turma(turma_id)

    # paginação
    page_str = request.GET.get("page", "1")
    try:
        page = max(1, int(page_str))
    except Exception:
        page = 1
    page_obj = _paginate(qs, page=page, per_page=30)

    # métricas simples
    ocupacao = getattr(turma, "ocupacao_qtd", None)
    if ocupacao is None:
        try:
            ocupacao = turma.ocupacao  # property
        except Exception:
            ocupacao = qs.count()

    context = {
        "turma": turma,
        "page_obj": page_obj,
        "ocupacao": ocupacao,
        "capacidade": turma.capacidade,
        "vagas": max(0, turma.capacidade - ocupacao),
        "base_qs": "", "suffix": "",  # se quiser filtros depois
        "hoje": now().date(),
    }
    return render(request, "turmas/alunos.html", context)


@login_required
def desmatricular_view(request: HttpRequest, matricula_id: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    data_fim = request.POST.get("data_fim", "") or None
    try:
        d = None
        if data_fim:
            from datetime import date as _d
            y,m,dd = [int(x) for x in data_fim.split("-")]
            d = _d(y,m,dd)
        # precisamos descobrir a turma para redirecionar
        m = Matricula.objects.select_related("turma").filter(id=matricula_id, ativa=True).first()
        if not m:
            messages.error(request, "Matrícula não encontrada/ativa.")
            return redirect(reverse("turmas:list"))
        turma_id = m.turma_id
        ts.desmatricular(matricula_id, data_fim=d)
        messages.success(request, "Matrícula encerrada.")
        return redirect(reverse("turmas:alunos", args=[turma_id]))
    except Exception as e:
        messages.error(request, f"Falha ao desmatricular: {e}")
        return redirect(reverse("turmas:list"))
