from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpRequest
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import FuncionarioForm, FuncionarioFiltroForm, ImportacaoExcelForm
from . import services as cs

@login_required
def list_funcionarios(request: HttpRequest):
    q = request.GET.get("q", "").strip()
    ativos_param = request.GET.get("ativos", "")
    if   ativos_param == "1": ativos = True
    elif ativos_param == "0": ativos = False
    else:                     ativos = None

    qs = cs.buscar_funcionarios(q=q, ativos=ativos)

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

    filtro_form = FuncionarioFiltroForm(initial={"q": q, "ativos": ativos_param})
    form = FuncionarioForm()
    import_form = ImportacaoExcelForm()

    return render(request, "funcionarios/list.html", {
        "page_obj": page_obj,
        "filtro_form": filtro_form,
        "form": form,
        "import_form": import_form,
        "q": q, "ativos_param": ativos_param,
        "base_qs": base_qs, "suffix": suffix,
    })

@login_required
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
        messages.error(request, "Dados inválidos.")
    return redirect(reverse("funcionarios:list"))

@login_required
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
def exportar_funcionarios_view(request: HttpRequest):
    filename, content = cs.exportar_funcionarios_para_excel()
    resp = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename=\"{filename}\"'
    return resp

@login_required
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
