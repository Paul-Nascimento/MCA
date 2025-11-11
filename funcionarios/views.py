from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpRequest
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import FuncionarioForm, FuncionarioFiltroForm, ImportacaoExcelForm
from . import services as cs
from .models import Funcionario

from django.core.paginator import Paginator

from django.contrib.auth.decorators import login_required, user_passes_test

def is_diretor(user):
    return user.groups.filter(name='Diretoria').exists() or user.is_superuser

def is_professor(user):
    return user.groups.filter(name='Professor').exists()

def is_estagiario(user):
    return user.groups.filter(name='Estagiario').exists()

@login_required
@user_passes_test(is_diretor,login_url='/turmas/')
def list_funcionarios(request):
    q = request.GET.get("q", "").strip()
    ativo = request.GET.get("ativo")
    regime = request.GET.get("regime")
    cargo = request.GET.get("cargo")

    ativo_bool = None
    if ativo in ("1", "0"):
        ativo_bool = (ativo == "1")

    qs = cs.buscar_funcionarios(q=q, ativo=ativo_bool, regime=regime, cargo=cargo)

    page = max(1, int(request.GET.get("page", "1") or 1))
    page_obj = Paginator(qs, 20).get_page(page)

    return render(request, "funcionarios/list.html", {
        "page_obj": page_obj,
        "q": q,
        "ativo": ativo,
        "regime": regime,
        "cargo": cargo,
        "CARGOS": Funcionario.Cargo.choices,
        "REGIMES": Funcionario.RegimeTrabalhista.choices,
        "base_qs": f"&q={q}&ativo={ativo}&regime={regime}&cargo={cargo}",
        "funcionario_form": FuncionarioForm()  # form no modal (vazio)
    })

@login_required
@user_passes_test(is_diretor,login_url='/turmas/')
def create_funcionario(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")

    form = FuncionarioForm(request.POST)
    if form.is_valid():
        try:
            cs.criar_funcionario(form.cleaned_data)
            messages.success(request, "Funcionário criado com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao criar: {e}")
    else:
        messages.error(request, "Dados inválidos. Verifique os campos obrigatórios.")

    return redirect(reverse("funcionarios:list"))

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def update_funcionario(request: HttpRequest, pk: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")

    form = FuncionarioForm(request.POST)
    if form.is_valid():
        try:
            cs.atualizar_funcionario(pk, form.cleaned_data)
            messages.success(request, "Funcionário atualizado com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao atualizar: {e}")
    else:
        messages.error(request, "Dados inválidos.")

    return redirect(reverse("funcionarios:list"))

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def exportar_funcionarios_view(request: HttpRequest):
    filename, content = cs.exportar_funcionarios_para_excel()
    resp = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename=\"{filename}\"'
    return resp

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def importar_funcionarios_view(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")

    form = ImportacaoExcelForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Envie um arquivo .xlsx válido.")
        return redirect(reverse("funcionarios:list"))

    try:
        rel = cs.importar_funcionarios_de_excel(request.FILES["arquivo"])
        messages.success(
            request,
            f"Importação: {rel.get('sucesso',0)} OK, "
            f"{rel.get('criados',0)} criados, {rel.get('atualizados',0)} atualizados. "
            f"{len(rel.get('erros',[]))} erros."
        )
        erros = rel.get("erros", [])
        if erros:
            preview = "; ".join(f"L{e['linha']}: {e['erro']}" for e in erros[:3])
            messages.warning(request, f"Erros (parcial): {preview}")
    except Exception as e:
        messages.error(request, f"Falha na importação: {e}")

    return redirect(reverse("funcionarios:list"))
