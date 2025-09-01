from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponseBadRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from .forms import TurmaForm, TurmaFiltroForm, MatriculaForm
from .models import Turma, DIAS_SEMANA
from . import services as cs
from funcionarios.models import Funcionario
from modalidades.models import Modalidade
from condominios.models import Condominio
from clientes.models import Cliente

@login_required
def list_turmas(request: HttpRequest):
    # filtros
    q = request.GET.get("q", "").strip()
    condominio_id = request.GET.get("condominio") or None
    modalidade_id = request.GET.get("modalidade") or None
    professor_id = request.GET.get("professor") or None
    dia_param = request.GET.get("dia_semana", "")
    ativos_param = request.GET.get("ativos", "")

    dia_semana = int(dia_param) if (dia_param not in ("", None)) else None
    if   ativos_param == "1": ativos = True
    elif ativos_param == "0": ativos = False
    else:                     ativos = None

    qs = cs.buscar_turmas(
        q=q,
        condominio_id=int(condominio_id) if condominio_id else None,
        modalidade_id=int(modalidade_id) if modalidade_id else None,
        professor_id=int(professor_id) if professor_id else None,
        dia_semana=dia_semana,
        ativos=ativos
    )

    # Ocupação "hoje": matriculas ativas com data_inicio <= hoje e (data_fim is null ou >= hoje)
    # DEPOIS (apenas matrículas ativas)
    from django.db.models import Count, Q
    qs = qs.annotate(
        ocupacao=Count("matriculas", filter=Q(matriculas__ativa=True))
    )


    # paginação segura
    page_str = request.GET.get("page", "1")
    try:
        page = int(page_str)
        if page < 1: page = 1
    except (TypeError, ValueError):
        page = 1

    page_obj = cs.paginar_queryset(qs, page=page, per_page=20)

    # querystring base (sem page)
    qd = request.GET.copy()
    qd.pop("page", None)
    base_qs = qd.urlencode()
    suffix = f"&{base_qs}" if base_qs else ""

    filtro_form = TurmaFiltroForm(initial={
        "q": q,
        "condominio": condominio_id,
        "modalidade": modalidade_id,
        "professor": professor_id,
        "dia_semana": dia_param,
        "ativos": ativos_param,
    })
    turma_form = TurmaForm()
    matricula_form = MatriculaForm()

    # selects para os modais
    professores = Funcionario.objects.filter(ativo=True).order_by("nome")
    modalidades = Modalidade.objects.all().order_by("nome")
    condominios = Condominio.objects.all().order_by("nome")
    clientes = Cliente.objects.filter(ativo=True).order_by("nome_razao")[:500]

    return render(request, "turmas/list.html", {
        "page_obj": page_obj,
        "filtro_form": filtro_form,
        "turma_form": turma_form,
        "matricula_form": matricula_form,
        "professores": professores,
        "modalidades": modalidades,
        "condominios": condominios,
        "clientes": clientes,
        "DIAS_SEMANA": DIAS_SEMANA,
        "q": q, "condominio_id": condominio_id, "modalidade_id": modalidade_id,
        "professor_id": professor_id, "dia_param": dia_param, "ativos_param": ativos_param,
        "base_qs": base_qs, "suffix": suffix,
    })

@login_required
def create_turma(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = TurmaForm(request.POST)
    if form.is_valid():
        cd = form.cleaned_data
        try:
            t = cs.criar_turma({
                "professor_id": cd["professor"].id,
                "modalidade_id": cd["modalidade"].id,
                "condominio_id": cd["condominio"].id,
                "nome_exibicao": cd.get("nome_exibicao") or "",
                "valor": cd["valor"],
                "capacidade": cd["capacidade"],
                "dia_semana": cd["dia_semana"],
                "hora_inicio": cd["hora_inicio"],
                "duracao_minutos": cd["duracao_minutos"],
                "inicio_vigencia": cd["inicio_vigencia"],
                "fim_vigencia": cd.get("fim_vigencia"),
                "ativo": cd["ativo"],
            })
            messages.success(request, "Turma criada com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao criar turma: {e}")
    else:
        messages.error(request, "Dados inválidos no formulário da turma.")
    return redirect(reverse("turmas:list"))

@login_required
def update_turma(request: HttpRequest, pk: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = TurmaForm(request.POST)
    if form.is_valid():
        cd = form.cleaned_data
        try:
            t = cs.atualizar_turma(pk, {
                "professor_id": cd["professor"].id,
                "modalidade_id": cd["modalidade"].id,
                "condominio_id": cd["condominio"].id,
                "nome_exibicao": cd.get("nome_exibicao") or "",
                "valor": cd["valor"],
                "capacidade": cd["capacidade"],
                "dia_semana": cd["dia_semana"],
                "hora_inicio": cd["hora_inicio"],
                "duracao_minutos": cd["duracao_minutos"],
                "inicio_vigencia": cd["inicio_vigencia"],
                "fim_vigencia": cd.get("fim_vigencia"),
                "ativo": cd["ativo"],
            })
            messages.success(request, "Turma atualizada com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao atualizar turma: {e}")
    else:
        messages.error(request, "Dados inválidos no formulário da turma.")
    return redirect(reverse("turmas:list"))

# turmas/views.py
@login_required
def matricular_cliente_view(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = MatriculaForm(request.POST)

    print('Iniciando form')
    if not form.is_valid():
        print(form.errors.as_json())
        # 👇 Mostre o detalhe do erro
        messages.error(request, f"Dados inválidos na matrícula: {form.errors.as_json()}")
        return redirect(reverse("turmas:list"))
    cd = form.cleaned_data
    try:
        cs.matricular_cliente(
            turma_id=cd["turma_id"],
            cliente_id=cd["cliente"].id,
            data_inicio=cd.get("data_inicio"),
        )
        print('teste')
        messages.success(request, "Cliente matriculado com sucesso.")
    except Exception as e:
        print(e)
        messages.error(request, f"Falha na matrícula: {e}")
    return redirect(reverse("turmas:list"))


@login_required
def exportar_turmas_view(request: HttpRequest):
    # Reaproveita os filtros da listagem
    q = request.GET.get("q", "").strip()
    condominio_id = int(request.GET.get("condominio")) if request.GET.get("condominio") else None
    modalidade_id = int(request.GET.get("modalidade")) if request.GET.get("modalidade") else None
    professor_id  = int(request.GET.get("professor")) if request.GET.get("professor") else None
    dia_param     = request.GET.get("dia_semana", "")
    dia_semana    = int(dia_param) if dia_param not in ("", None) else None
    ativos_param  = request.GET.get("ativos", "")
    if   ativos_param == "1": ativos = True
    elif ativos_param == "0": ativos = False
    else:                     ativos = None

    qs = cs.buscar_turmas(
        q=q, condominio_id=condominio_id, modalidade_id=modalidade_id,
        professor_id=professor_id, dia_semana=dia_semana, ativos=ativos
    ).select_related("modalidade","condominio","professor")

    filename, content = cs.exportar_turmas_para_excel(qs)
    resp = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp

@login_required
def turma_alunos(request: HttpRequest, pk: int):
    turma = Turma.objects.select_related("modalidade","condominio","professor").filter(id=pk).first()
    if not turma:
        messages.error(request, "Turma não encontrada.")
        return redirect(reverse("turmas:list"))

    hoje = date.today()
    matriculas = (turma.matriculas.select_related("cliente").order_by("-ativa","cliente__nome_razao","id"))
    ocupacao = cs.contar_matriculas(turma)

    return render(request, "turmas/alunos.html", {
        "turma": turma,
        "matriculas": matriculas,
        "ocupacao": ocupacao,
        "hoje": hoje,
    })

@login_required
def encerrar_matricula_view(request: HttpRequest, matricula_id: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    try:
        m = cs.encerrar_matricula(matricula_id)
        messages.success(request, f"Matrícula do cliente encerrada em {m.data_fim}.")
        return redirect(reverse("turmas:alunos", args=[m.turma_id]))
    except Exception as e:
        messages.error(request, f"Não foi possível encerrar: {e}")
        # melhor esforço para voltar para a turma
        ref = request.POST.get("turma_id")
        return redirect(reverse("turmas:alunos", args=[ref]) if ref else reverse("turmas:list"))


# turmas/views_presenca.py

@login_required
def criar_lista_presenca_view(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = ListaPresencaCreateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Dados inválidos para criar lista.")
        # ⚠️ tenta obter um turma_id bruto do POST para redirecionar melhor
        return _redir_presencas_turma(request, request.POST.get("turma_id", ""), "Turma inválida.")
    turma_id = form.cleaned_data.get("turma_id")
    d = form.cleaned_data["data"]
    obs = form.cleaned_data.get("observacao_geral","") or ""
    try:
        lista = cs.criar_lista_presenca(turma_id=turma_id, d=d, observacao_geral=obs)
        messages.success(request, f"Lista de {d:%d/%m/%Y} criada.")
        return redirect(reverse("turmas:presenca_detalhe", args=[lista.id]))
    except cs.ListaJaExiste:
        messages.warning(request, "Já existe lista para essa data.")
        return _redir_presencas_turma(request, turma_id)
    except Exception as e:
        messages.error(request, f"Não foi possível criar a lista: {e}")
        return _redir_presencas_turma(request, turma_id, "Falha ao criar a lista.")

@login_required
def gerar_listas_automaticas_view(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = ListaPresencaRangeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Período inválido para geração automática.")
        return _redir_presencas_turma(request, request.POST.get("turma_id", ""))
    turma_id = form.cleaned_data.get("turma_id")
    d1 = form.cleaned_data["data_de"]
    d2 = form.cleaned_data["data_ate"]
    try:
        rel = cs.gerar_listas_automaticas(turma_id=turma_id, data_de=d1, data_ate=d2)
        messages.success(request, f"Gerado: {rel['criadas']} nova(s). Já existiam: {rel['existentes']}. Fora da vigência: {rel['ignoradas_fora_vigencia']}.")
    except Exception as e:
        messages.error(request, f"Falha na geração: {e}")
    return _redir_presencas_turma(request, turma_id)
