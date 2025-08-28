from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from .forms import ClienteForm, ClienteFiltroForm, ImportacaoExcelForm
from . import services as cs

# views.py
from .models import UF_CHOICES




from django.utils.http import urlencode

@login_required
def list_clientes(request):
    # filtros
    q = request.GET.get("q", "").strip()
    ativos_param = request.GET.get("ativos", "")
    if ativos_param == "1":
        ativos = True
    elif ativos_param == "0":
        ativos = False
    else:
        ativos = None

    qs = cs.buscar_clientes(q=q, ativos=ativos)

    # 🔒 Sanitiza o page para evitar "2&q="
    page_str = request.GET.get("page", "1")
    try:
        page = int(page_str)
        if page < 1:
            page = 1
    except (TypeError, ValueError):
        page = 1

    page_obj = cs.paginar_queryset(qs, page=page, per_page=20)

    # 🔗 Querystring base (sem o parâmetro page)
    qd = request.GET.copy()
    qd.pop("page", None)
    base_qs = qd.urlencode()  # ex.: "q=joao&ativos=1" ou ""

    filtro_form = ClienteFiltroForm(initial={"q": q, "ativos": ativos_param})
    cliente_form = ClienteForm()
    import_form = ImportacaoExcelForm()

    return render(
        request,
        "clientes/list.html",
        {
            "page_obj": page_obj,
            "filtro_form": filtro_form,
            "cliente_form": cliente_form,
            "import_form": import_form,
            "q": q,
            "ativos_param": ativos_param,
            "base_qs": base_qs,  # 👈 passa pro template
        },
    )


@login_required
def create_cliente(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = ClienteForm(request.POST)
    if form.is_valid():
        try:
            cs.criar_cliente(form.cleaned_data)
            messages.success(request, "Cliente criado com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao criar cliente: {e}")
    else:
        messages.error(request, "Dados inválidos no formulário.")
    return redirect(reverse("clientes:list"))

@login_required
def update_cliente(request: HttpRequest, pk: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = ClienteForm(request.POST)
    if form.is_valid():
        try:
            cs.atualizar_cliente(pk, form.cleaned_data)
            messages.success(request, "Cliente atualizado com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao atualizar: {e}")
    else:
        messages.error(request, "Dados inválidos no formulário.")
    return redirect(reverse("clientes:list"))

@login_required
def exportar_clientes_view(request: HttpRequest):
    filename, content = cs.exportar_clientes_para_excel()
    resp = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp

@login_required
def importar_clientes_view(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = ImportacaoExcelForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Envie um arquivo .xlsx válido.")
        return redirect(reverse("clientes:list"))

    try:
        rel = cs.importar_clientes_de_excel(request.FILES["arquivo"])
        ok = rel.get("sucesso", 0)
        criados = rel.get("criados", 0)
        atualizados = rel.get("atualizados", 0)
        vincs = rel.get("vinculos_criados", 0)
        erros = rel.get("erros", [])

        messages.success(
            request,
            f"Importação concluída: {ok} linhas OK, {criados} criados, "
            f"{atualizados} atualizados, {vincs} vínculos. "
            f"{len(erros)} erros."
        )
        if erros:
            # Mostra somente os 3 primeiros erros para não poluir a interface
            preview = "; ".join(f"L{e['linha']}: {e['erro']}" for e in erros[:3])
            messages.warning(request, f"Erros (parcial): {preview}")
    except Exception as e:
        messages.error(request, f"Falha na importação: {e}")

    return redirect(reverse("clientes:list"))
