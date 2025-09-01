# clientes/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest

from .forms import ClienteForm, ClienteFiltroForm
from . import services as cs

@login_required
def list_clientes(request: HttpRequest):
    f = ClienteFiltroForm(request.GET or None)
    cd = f.cleaned_data if f.is_valid() else {}
    qs = cs.buscar_clientes(
        q=cd.get("q",""),
        ativos=(None if (cd.get("ativos") in (None,"")) else (cd.get("ativos") == "1"))
    )
    # paginação segura
    page_str = request.GET.get("page", "1")
    try:
        page = max(1, int(page_str))
    except Exception:
        page = 1
    page_obj = cs.paginar(qs, page=page, per_page=20)

    qd = request.GET.copy(); qd.pop("page", None)
    base_qs = qd.urlencode()
    suffix = f"&{base_qs}" if base_qs else ""

    return render(request, "clientes/list.html", {
        "filtro_form": f,
        "page_obj": page_obj,
        "suffix": suffix,
        "base_qs": base_qs,
        "cliente_form": ClienteForm(),
    })

@login_required
def create_cliente(request: HttpRequest):
    if request.method != "POST": return HttpResponseBadRequest("Somente POST.")
    form = ClienteForm(request.POST)
    if form.is_valid():
        try:
            cs.criar_cliente(form.cleaned_data)
            messages.success(request, "Cliente criado.")
        except Exception as e:
            messages.error(request, f"Erro ao criar: {e}")
    else:
        messages.error(request, f"Dados inválidos: {form.errors.as_json()}")
    return redirect(reverse("clientes:list"))

@login_required
def update_cliente(request: HttpRequest, pk: int):
    if request.method != "POST": return HttpResponseBadRequest("Somente POST.")
    form = ClienteForm(request.POST)
    if form.is_valid():
        try:
            cs.atualizar_cliente(pk, form.cleaned_data)
            messages.success(request, "Cliente atualizado.")
        except Exception as e:
            messages.error(request, f"Erro ao atualizar: {e}")
    else:
        messages.error(request, f"Dados inválidos: {form.errors.as_json()}")
    return redirect(reverse("clientes:list"))

@login_required
def ativar_cliente(request: HttpRequest, pk: int):
    if request.method != "POST": return HttpResponseBadRequest("Somente POST.")
    try:
        ativo = request.POST.get("ativo","1") == "1"
        cs.ativar(pk, ativo=ativo)
        messages.success(request, "Cliente atualizado.")
    except Exception as e:
        messages.error(request, f"Erro: {e}")
    return redirect(reverse("clientes:list"))

@login_required
def importar_excel_view(request: HttpRequest):
    if request.method != "POST": return HttpResponseBadRequest("Somente POST.")
    f = request.FILES.get("arquivo")
    if not f:
        messages.error(request, "Selecione um arquivo .xlsx")
        return redirect(reverse("clientes:list"))
    try:
        rel = cs.importar_excel(f)
        messages.success(request, f"Importação: criados={rel['created']} atualizados={{rel['updated']}} ignorados={rel['skipped']}")
    except Exception as e:
        messages.error(request, f"Falha ao importar: {e}")
    return redirect(reverse("clientes:list"))

@login_required
def exportar_excel_view(request: HttpRequest):
    qs = cs.buscar_clientes(
        q=request.GET.get("q",""),
        ativos=None if request.GET.get("ativos","") == "" else request.GET.get("ativos")=="1"
    )
    filename, content = cs.exportar_excel(qs)
    resp = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
