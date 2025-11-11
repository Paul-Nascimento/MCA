from __future__ import annotations

from typing import Optional
from datetime import date as _date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.core.exceptions import ValidationError
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

from django.contrib.auth.decorators import login_required, user_passes_test

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
# 📌 LISTAGEM DE TURMAS
# ------------------------------------------------------------
def is_diretor(user):
    return user.groups.filter(name='Diretoria').exists() or user.is_superuser

def is_professor(user):
    return user.groups.filter(name='Professor').exists()

def is_estagiario(user):
    return user.groups.filter(name='Estagiario').exists()




@login_required
def list_turmas(request: HttpRequest) -> HttpResponse:

    user = request.user

    # Se for professor, exibe apenas as turmas dele
    if hasattr(user, "funcionario") and user.funcionario.cargo == "PROF":
        turmas = Turma.objects.filter(professor=user.funcionario)
    else:
        turmas = Turma.objects.all()


    q = (request.GET.get("q") or "").strip()
    condominio_id = request.GET.get("condominio") or ""
    modalidade_id = request.GET.get("modalidade") or ""
    professor_id = request.GET.get("professor") or ""
    dia_param = request.GET.get("dia_semana") or ""
    ativos_param = request.GET.get("ativos", "")

    qs = ts.buscar_turmas(
        q=q,
        condominio_id=int(condominio_id) if condominio_id else None,
        modalidade_id=int(modalidade_id) if modalidade_id else None,
        professor_id=int(professor_id) if professor_id else None,
        dia_semana=int(dia_param) if dia_param else None,
        ativos=(None if ativos_param == "" else (ativos_param == "1")),
    )

    if hasattr(request.user, "funcionario") and request.user.funcionario.cargo == "PROF":
        qs = qs.filter(professor=request.user.funcionario)

    page = max(1, int(request.GET.get("page", "1") or 1))
    page_obj = Paginator(qs, 20).get_page(page)

    # Combos de filtro
    try:
        from condominios.models import Condominio
        condominios = Condominio.objects.filter(modalidade__isnull=False).distinct()
    except Exception:
        condominios = []

    modalidades = Modalidade.objects.all().order_by("nome")
    professores = Funcionario.objects.filter(ativo=True).order_by("nome")

    # Clientes (para modal de matrícula, se existir)
    clientes = []
    if Cliente is not None:
        clientes = Cliente.objects.filter(ativo=True).order_by("nome_razao")[:500]

    # Query string para manter filtros
    def _v(v: str) -> str:
        return v if v is not None else ""
    base_qs = f"q={_v(q)}&condominio={_v(condominio_id)}&modalidade={_v(modalidade_id)}&professor={_v(professor_id)}&dia_semana={_v(dia_param)}&ativos={_v(ativos_param)}"
    suffix = "&" + base_qs if base_qs else ""

    ctx = {
        "page_obj": page_obj,
        "q": q,
        "condominio_id": str(condominio_id),
        "modalidade_id": str(modalidade_id),
        "professor_id": str(professor_id),
        "dia_param": str(dia_param),
        "ativos_param": ativos_param,

        "condominios": condominios,
        "modalidades": modalidades,
        "professores": professores,
        "clientes": clientes,

        "DIAS_SEMANA": DIAS_SEMANA,

        "base_qs": base_qs,
        "suffix": suffix,
    }
    return render(request, "turmas/list.html", ctx)

# ------------------------------------------------------------
# CREATE / UPDATE
# ------------------------------------------------------------

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
@require_POST
def create_turma(request: HttpRequest) -> HttpResponse:
    """
    Criação de nova turma com validação completa.
    """
    form = TurmaForm(request.POST or None)
    if not form.is_valid():
        messages.error(
            request,
            "Erro ao validar a turma: " + "; ".join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()])
        )
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
@user_passes_test(is_diretor,login_url="/turmas/")
@require_POST
def update_turma(request: HttpRequest, turma_id: int) -> HttpResponse:
    """
    Atualização de turma existente.
    """
    form = TurmaForm(request.POST or None)
    if not form.is_valid():
        messages.error(
            request,
            "Erro ao validar a turma: " + "; ".join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()])
        )
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
# EXPORTAÇÃO
# ------------------------------------------------------------

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def exportar_turmas(request: HttpRequest) -> HttpResponse:
    """
    Exporta turmas para Excel respeitando filtros atuais da lista.
    """
    q = (request.GET.get("q") or "").strip()
    condominio_id = request.GET.get("condominio") or ""
    modalidade_id = request.GET.get("modalidade") or ""
    professor_id = request.GET.get("professor") or ""
    dia_param = request.GET.get("dia_semana") or ""
    ativos_param = request.GET.get("ativos", "")

    qs = ts.buscar_turmas(
        q=q,
        condominio_id=int(condominio_id) if condominio_id else None,
        modalidade_id=int(modalidade_id) if modalidade_id else None,
        professor_id=int(professor_id) if professor_id else None,
        dia_semana=int(dia_param) if dia_param else None,
        ativos=(None if ativos_param == "" else (ativos_param == "1")),
    )

    filename, content = ts.exportar_turmas_excel(qs)
    resp = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp

# ------------------------------------------------------------
# Alunos de uma turma (visualização detalhada da turma)
# ------------------------------------------------------------

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
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
        qs = (
            turma.matriculas
            .select_related("cliente")
            .filter(ativa=True)
            .order_by("cliente__nome_razao")
        )
    except Exception:
        qs = []

    page = max(1, int(request.GET.get("page", 1)))
    page_obj = Paginator(qs, 20).get_page(page)

    vagas = max(0, turma.capacidade - turma.ocupacao)

    return render(
        request,
        "turmas/alunos.html",
        {"turma": turma, "page_obj": page_obj, "vagas": vagas},
    )


# ------------------------------------------------------------
# Matrícula de cliente em turma
# ------------------------------------------------------------
@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
@require_POST
def matricular_view(request: HttpRequest) -> HttpResponse:
    try:
        turma_id = int(request.POST.get("turma_id") or 0)
        cliente_id = int(request.POST.get("cliente") or 0)
        data_inicio = request.POST.get("data_inicio")

        participante_nome = request.POST.get("participante_nome") or ""
        participante_data_nascimento = request.POST.get("participante_data_nascimento") or ""  # ✅ novo campo
        participante_sexo = request.POST.get("participante_sexo") or ""

        # checkbox "é o próprio cliente"
        raw_flag = request.POST.get("proprio_cliente") or request.POST.get("chkProprioAluno") or "on"
        proprio_cliente = str(raw_flag).lower() in ("on", "true", "1")

        # Se o usuário preencheu dados de participante, NÃO é o próprio cliente
        if any([participante_nome.strip(), participante_data_nascimento.strip(), participante_sexo.strip()]):
            proprio_cliente = False

        if not turma_id or not cliente_id or not data_inicio:
            messages.error(request, "Informe turma, cliente e data de início.")
            return redirect(reverse("turmas:list"))

        # Converter data de início da matrícula
        from datetime import date as _date
        y, m, d = [int(x) for x in data_inicio.split("-")]
        data_inicio_dt = _date(y, m, d)

        # Converter data de nascimento (se informada)
        participante_data_nascimento_dt = None
        if participante_data_nascimento:
            try:
                y2, m2, d2 = [int(x) for x in participante_data_nascimento.split("-")]
                participante_data_nascimento_dt = _date(y2, m2, d2)
            except ValueError:
                messages.error(request, "Data de nascimento do participante inválida.")
                return redirect(reverse("turmas:list"))

        # Chamar service
        ts.matricular_cliente(
            turma_id=turma_id,
            cliente_id=cliente_id,
            data_inicio=data_inicio_dt,
            participante_nome=participante_nome,
            participante_data_nascimento=participante_data_nascimento_dt,  # ✅ alterado
            participante_sexo=participante_sexo,
            proprio_cliente=proprio_cliente,
        )

    except ValidationError as e:
        messages.error(request, f"Não foi possível matricular: {e}")
    except Exception as e:
        messages.error(request, f"Erro ao matricular: {e}")
    else:
        messages.success(request, "Matrícula realizada com sucesso.")

    return redirect(reverse("turmas:list"))



# ------------------------------------------------------------
# Desmatricular aluno da turma
# ------------------------------------------------------------

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def desmatricular_view(request: HttpRequest, matricula_id: int) -> HttpResponse:
    try:
        ts.desmatricular(matricula_id)
    except ValidationError as e:
        messages.error(request, f"Não foi possível desmatricular: {e}")
    except Exception as e:
        messages.error(request, f"Erro ao desmatricular: {e}")
    else:
        messages.success(request, "Matrícula desativada.")
    return redirect(reverse("turmas:list"))


# ------------------------------------------------------------
# Alternar status ativo/inativo da turma
# ------------------------------------------------------------

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def toggle_status(request: HttpRequest, turma_id: int) -> HttpResponse:
    try:
        ts.toggle_status(turma_id)
    except Exception as e:
        messages.error(request, f"Não foi possível alterar o status: {e}")
    else:
        messages.success(request, "Status da turma atualizado com sucesso.")
    return redirect(reverse("turmas:list"))


# ------------------------------------------------------------
# Selecionar cliente dentro de um modal ou popup (iframe)
# ------------------------------------------------------------

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def selecionar_cliente(request: HttpRequest, turma_id: int) -> HttpResponse:
    turma = (
        Turma.objects
        .select_related("modalidade__condominio", "professor")
        .filter(id=turma_id)
        .first()
    )

    if not turma:
        return HttpResponseBadRequest("Turma inválida.")

    clientes = []
    if Cliente:
        # ✅ Só lista clientes do mesmo condomínio da modalidade da turma
        clientes = (
            Cliente.objects
            .filter(condominio=turma.modalidade.condominio, ativo=True)
            .order_by("nome_razao")
        )

    return render(
        request,
        "turmas/selecionar_cliente.html",
        {
            "turma": turma,
            "clientes": clientes,
            "embed": request.GET.get("embed") == "1",
        }
    )


# turmas/views.py
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_POST
from datetime import date as _date
from .forms import MatriculaForm
from .models import Matricula

@user_passes_test(is_diretor,login_url="/turmas/")
@login_required
def matriculas_turma_view(request: HttpRequest, turma_id: int) -> HttpResponse:
    turma = (
        Turma.objects
        .select_related("modalidade__condominio", "professor")
        .filter(id=turma_id)
        .first()
    )
    if not turma:
        messages.error(request, "Turma não encontrada.")
        return redirect(reverse("turmas:list"))

    condominio = turma.modalidade.condominio

    # 🔎 Filtros básicos de busca
    q = (request.GET.get("q") or "").strip()
    clientes_qs = Cliente.objects.filter(condominio=condominio, ativo=True)
    if q:
        clientes_qs = clientes_qs.filter(
            Q(nome_razao__icontains=q) |
            Q(cpf_cnpj__icontains=q)
        )

    # paginação
    page = max(1, int(request.GET.get("page", "1") or 1))
    page_obj = Paginator(clientes_qs.order_by("nome_razao"), 20).get_page(page)

    # Matrículas já existentes
    matriculas_existentes = Matricula.objects.filter(turma=turma, ativa=True)
    matriculados_ids = set(matriculas_existentes.values_list("cliente_id", flat=True))
    matriculas_proprias = matriculas_existentes.filter(participante_nome__exact="")

    form = MatriculaForm(initial={"turma_id": turma.id})

    ctx = {
        "turma": turma,
        "condominio": condominio,
        "clientes_page": page_obj,
        "matriculas":matriculas_proprias,
        "matriculados_ids": matriculados_ids,
        "form": form,
        "q": q,
    }
    return render(request, "turmas/matriculas_list.html", ctx)


from datetime import date
@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
@require_POST
def matricular_cliente_direto(request: HttpRequest, turma_id: int) -> HttpResponse:
    form = MatriculaForm(request.POST)
    cliente_id = request.POST.get("cliente_id")
    print(cliente_id,form.data)
    if not form.is_valid():
        messages.error(request, "Dados inválidos para matrícula.")
        print('erro',request)
        #return redirect(reverse("turmas:matriculas_turma", args=[turma_id]))

    try:
        data = form.data
        ts.matricular_cliente(
            turma_id=turma_id,
            cliente_id=data["cliente"],
            data_inicio=date.today(),
            participante_nome=data.get("participante_nome") or "",
            participante_data_nascimento=data.get("participante_data_nascimento") or "",
            participante_sexo=data.get("participante_sexo") or "",
            proprio_cliente=not bool(data.get("participante_nome")),
        )
        messages.success(request, "Matrícula criada com sucesso.")
    except Exception as e:
        print(e )
        messages.error(request, f"Erro ao matricular: {e}")

    return redirect(reverse("turmas:matriculas_turma", args=[turma_id]))





@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
@require_POST
def cadastrar_dependente_view(request: HttpRequest) -> HttpResponse:
    from . import services as ts

    try:
        turma_id = request.POST.get("turma_id")
        cliente_id = request.POST.get("cliente_id")
        participante_nome = (request.POST.get("participante_nome") or "").strip()
        participante_data_nascimento = request.POST.get("participante_data_nascimento")
        participante_sexo = request.POST.get("participante_sexo")
        data_inicio_str = request.POST.get("data_inicio")

        # 🧩 Log de debug opcional
        print(f"[DEBUG] turma_id={turma_id}, cliente_id={cliente_id}, participante={participante_nome}, nascimento={participante_data_nascimento}, sexo={participante_sexo}, data_inicio={data_inicio_str}")

        # 🔍 Validação básica
        if not turma_id or not cliente_id or not participante_nome:
            messages.error(request, "Preencha os campos obrigatórios.")
            return redirect(request.META.get("HTTP_REFERER", reverse("turmas:list")))

        # ✅ Converter data de nascimento (opcional)
        participante_data_nasc_dt = None
        if participante_data_nascimento:
            try:
                y, m, d = [int(x) for x in participante_data_nascimento.split("-")]
                participante_data_nasc_dt = _date(y, m, d)
            except Exception:
                messages.error(request, "Data de nascimento inválida.")
                return redirect(request.META.get("HTTP_REFERER", reverse("turmas:list")))

        # ✅ Converter data de início (obrigatória)
        if not data_inicio_str:
            data_inicio = _date.today()
        else:
            try:
                y2, m2, d2 = [int(x) for x in data_inicio_str.split("-")]
                data_inicio = _date(y2, m2, d2)
            except Exception:
                messages.error(request, "Data de início inválida.")
                return redirect(request.META.get("HTTP_REFERER", reverse("turmas:list")))

        # ✅ Chama o service que já cria a matrícula
        matricula = ts.matricular_cliente(
            turma_id=turma_id,
            cliente_id=cliente_id,
            data_inicio=data_inicio,
            participante_nome=participante_nome,
            participante_data_nascimento=participante_data_nasc_dt,
            participante_sexo=participante_sexo,
            proprio_cliente=False,
        )

        # 🔔 Mensagem de sucesso
        if matricula:
            messages.success(request, f"Dependente '{participante_nome}' matriculado com sucesso!")
        else:
            messages.warning(request, "A matrícula não foi criada — verifique regras de duplicidade.")

    except ValidationError as e:
        messages.error(request, f"Não foi possível cadastrar o dependente: {e}")
    except Exception as e:
        import traceback
        print("❌ Erro ao cadastrar dependente:", e)
        traceback.print_exc()
        messages.error(request, f"Erro inesperado ao matricular dependente: {e}")

    return redirect(request.META.get("HTTP_REFERER", reverse("turmas:list")))

