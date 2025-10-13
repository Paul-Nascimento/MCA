from __future__ import annotations
from typing import Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import TurmaForm
from .models import Turma
from . import services as ts

from modalidades.models import Modalidade
from funcionarios.models import Funcionario
try:
    from clientes.models import Cliente
except Exception:
    Cliente = None

DIAS_SEMANA = (
    (1, "Segunda"),
    (2, "Terça"),
    (3, "Quarta"),
    (4, "Quinta"),
    (5, "Sexta"),
    (6, "Sábado"),
    (7, "Domingo"),
)

# ------------------------------------------------------------
# Listagem
# ------------------------------------------------------------

@login_required
def list_turmas(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    condominio_id = request.GET.get("condominio") or ""
    modalidade_id = request.GET.get("modalidade") or ""
    professor_id  = request.GET.get("professor") or ""
    dia_param     = request.GET.get("dia_semana") or ""
    ativos_param  = request.GET.get("ativos", "")

    qs = ts.buscar_turmas(
        q=q,
        condominio_id=int(condominio_id) if condominio_id else None,
        modalidade_id=int(modalidade_id) if modalidade_id else None,
        professor_id=int(professor_id) if professor_id else None,
        dia_semana=int(dia_param) if dia_param else None,
        ativos=(None if ativos_param == "" else (ativos_param == "1")),
    )

    page = max(1, int(request.GET.get("page", "1") or 1))
    page_obj = Paginator(qs, 20).get_page(page)

    # combos de filtro
    try:
        from condominios.models import Condominio
        condominios = Condominio.objects.filter(modalidade__isnull=False).distinct()
    except Exception:
        condominios = []

    modalidades = Modalidade.objects.all().order_by("nome")
    professores = Funcionario.objects.filter(ativo=True).order_by("nome")

    # clientes para o modal de matrícula (limite 500)
    clientes = []
    if Cliente is not None:
        clientes = Cliente.objects.filter(ativo=True).order_by("nome_razao")[:500]

    # sufixo para manter filtros
    def _v(v: str) -> str:
        return v if v is not None else ""
    base_qs = f"q={_v(q)}&condominio={_v(condominio_id)}&modalidade={_v(modalidade_id)}&professor={_v(professor_id)}&dia_semana={_v(dia_param)}&ativos={_v(ativos_param)}"
    suffix = "&" + base_qs if base_qs else ""

    ctx = {
        "page_obj": page_obj,
        "filtro_form": {"initial": {"q": q}},
        "q": q,
        "condominio_id": str(condominio_id),
        "modalidade_id": str(modalidade_id),
        "professor_id": str(professor_id),
        "dia_param": str(dia_param),
        "ativos_param": ativos_param,
        "DIAS_SEMANA": DIAS_SEMANA,

        "condominios": condominios,
        "modalidades": modalidades,
        "professores": professores,
        "clientes": clientes,

        "base_qs": base_qs,
        "suffix": suffix,
    }
    return render(request, "turmas/list.html", ctx)

# ------------------------------------------------------------
# Create / Update
# ------------------------------------------------------------

@login_required
@require_POST
def create_turma(request: HttpRequest) -> HttpResponse:
    form = TurmaForm(request.POST or None)
    if not form.is_valid():
        messages.error(request, "Erro ao validar a turma: " + "; ".join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()]))
        return redirect(reverse("turmas:list"))
    try:
        ts.criar_turma(form.cleaned_data)
    except ValidationError as e:
        messages.error(request, f"Não foi possível criar a turma: {e}")
    except Exception as e:
        messages.error(request, f"Erro interno ao criar a turma: {e}")
    else:
        messages.success(request, "Turma criada com sucesso.")
    return redirect(reverse("turmas:list"))

@login_required
@require_POST
def update_turma(request: HttpRequest, turma_id: int) -> HttpResponse:
    form = TurmaForm(request.POST or None)
    if not form.is_valid():
        messages.error(request, "Erro ao validar a turma: " + "; ".join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()]))
        return redirect(reverse("turmas:list"))
    try:
        ts.atualizar_turma(turma_id, form.cleaned_data)
    except ValidationError as e:
        messages.error(request, f"Não foi possível atualizar a turma: {e}")
    except Exception as e:
        messages.error(request, f"Erro interno ao atualizar a turma: {e}")
    else:
        messages.success(request, "Turma atualizada com sucesso.")
    return redirect(reverse("turmas:list"))

# ------------------------------------------------------------
# Exportação
# ------------------------------------------------------------

@login_required
def exportar_turmas(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    condominio_id = request.GET.get("condominio") or ""
    modalidade_id = request.GET.get("modalidade") or ""
    professor_id  = request.GET.get("professor") or ""
    dia_param     = request.GET.get("dia_semana") or ""
    ativos_param  = request.GET.get("ativos", "")

    qs = ts.buscar_turmas(
        q=q,
        condominio_id=int(condominio_id) if condominio_id else None,
        modalidade_id=int(modalidade_id) if modalidade_id else None,
        professor_id=int(professor_id) if professor_id else None,
        dia_semana=int(dia_param) if dia_param else None,
        ativos=(None if ativos_param == "" else (ativos_param == "1")),
    )

    filename, content = ts.exportar_turmas_excel(qs)
    resp = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename=\"{filename}\"'
    return resp

# ------------------------------------------------------------
# Alunos da turma (link da listagem)
# ------------------------------------------------------------

@login_required
def alunos_turma(request: HttpRequest, turma_id: int) -> HttpResponse:
    turma = (
        Turma.objects
        .select_related("modalidade__condominio", "professor")
        .filter(id=turma_id)
        .first()
    )
    if not turma:
        messages.error(request, "Turma não encontrada.")
        return redirect(reverse("turmas:list"))

    try:
        from .models import Matricula
        alunos = (
                turma.matriculas
                    .select_related("cliente")
                    .filter(ativa=True)
                    .order_by("cliente__nome_razao")
            )
    except Exception:
        alunos = []

    return render(request, "turmas/alunos.html", {"turma": turma, "alunos": alunos})

# ------------------------------------------------------------
# Matrículas
# ------------------------------------------------------------

@login_required
@require_POST
def matricular_view(request: HttpRequest) -> HttpResponse:
    """
    Recebe POST do modal de matrícula.
    Campos esperados: turma_id, cliente, data_inicio, participante_* e "é o próprio" (chkProprioAluno no front).
    """
    try:
        turma_id = int(request.POST.get("turma_id") or 0)
        cliente_id = int(request.POST.get("cliente") or 0)
        data_inicio = request.POST.get("data_inicio")
        participante_nome = request.POST.get("participante_nome") or ""
        participante_cpf = request.POST.get("participante_cpf") or ""
        participante_sexo = request.POST.get("participante_sexo") or ""
        proprio_cliente = (request.POST.get("proprio_cliente") or request.POST.get("chkProprioAluno") or "on")
        proprio_cliente = str(proprio_cliente).lower() in ("1", "true", "on")

        print('Aq')
        print(participante_nome, participante_cpf, participante_sexo, proprio_cliente)
        if not turma_id or not cliente_id or not data_inicio:
            messages.error(request, "Informe turma, cliente e data de início.")
            return redirect(reverse("turmas:list"))

        from datetime import date as _date
        parts = [int(x) for x in str(data_inicio).split("-")]
        data_inicio_dt = _date(parts[0], parts[1], parts[2])

        ts.matricular_cliente(
            turma_id=turma_id,
            cliente_id=cliente_id,
            data_inicio=data_inicio_dt,
            participante_nome=participante_nome,
            participante_cpf=participante_cpf,
            participante_sexo=participante_sexo,
            proprio_cliente=proprio_cliente,
        )
    except ValidationError as e:
        print(e)
        messages.error(request, f"Não foi possível matricular: {e}")
    except Exception as e:
        print(e)
        messages.error(request, f"Erro interno ao matricular: {e}")
    else:
        messages.success(request, "Matrícula realizada com sucesso.")
    return redirect(reverse("turmas:list"))

@login_required
def desmatricular_view(request: HttpRequest, matricula_id: int) -> HttpResponse:
    try:
        ts.desmatricular(matricula_id)
    except ValidationError as e:
        messages.error(request, f"Não foi possível desmatricular: {e}")
    except Exception as e:
        messages.error(request, f"Erro interno ao desmatricular: {e}")
    else:
        messages.success(request, "Matrícula desativada.")
    return redirect(reverse("turmas:list"))

# ------------------------------------------------------------
# Toggle Ativo/Inativo da turma
# ------------------------------------------------------------

@login_required
def toggle_status(request: HttpRequest, turma_id: int) -> HttpResponse:
    try:
        ts.toggle_status(turma_id)
    except Exception as e:
        messages.error(request, f"Não foi possível alterar o status: {e}")
    else:
        messages.success(request, "Status da turma atualizado.")
    return redirect(reverse("turmas:list"))

# ------------------------------------------------------------
# Selecionar cliente (iframe)
# ------------------------------------------------------------

@login_required
def selecionar_cliente(request: HttpRequest, turma_id: int) -> HttpResponse:
    turma = (
        Turma.objects
        .select_related("modalidade__condominio", "professor")
        .filter(id=turma_id)
        .first()
    )
    if not turma:
        return HttpResponseBadRequest("Turma inválida.")

    if Cliente is None:
        clientes = []
    else:
        clientes = Cliente.objects.filter(condominio=turma.modalidade.condominio, ativo=True).order_by("nome_razao")

    return render(request, "turmas/selecionar_cliente.html", {
        "turma": turma,
        "clientes": clientes,
        "embed": request.GET.get("embed") == "1",
    })
