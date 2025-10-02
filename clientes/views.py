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
        q=cd.get("q", ""),
        ativos=(None if (cd.get("ativos") in (None,"")) else (cd.get("ativos") == "1")),
        condominio=cd.get("condominio")
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



from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from .models import Cliente


from django.utils import timezone
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from .models import Cliente

@login_required(False)  # aceite deve funcionar sem login; remova se estiver usando @login_required
def aceite_contrato(request, token: str):
    # 1) Busca cliente pelo token
    cliente = get_object_or_404(Cliente, aceite_token=token)

    # 2) Valida expiração
    if not cliente.aceite_expires_at or timezone.now() > cliente.aceite_expires_at:
        messages.error(request, "Link de confirmação expirado. Solicite um novo convite.")
        # opcional: página específica de expiração
        return render(request, "clientes/aceite_contrato.html", {"expirado": True, "cliente": cliente})

    # 3) Confirma aceite
    cliente.ativo = True
    cliente.aceite_confirmado_em = timezone.now()
    # Opcional: invalidar o token após o uso
    cliente.aceite_token = None
    cliente.aceite_expires_at = None
    cliente.save(update_fields=["ativo","aceite_confirmado_em","aceite_token","aceite_expires_at"])

    # 4) Página de sucesso
    return render(request, "clientes/aceite_sucesso.html", {"cliente": cliente})


