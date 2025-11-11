from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from .forms import CondominioForm, CondominioFiltroForm, ImportacaoExcelForm
from .models import UF_CHOICES
from . import services as cs


from django.contrib.auth.decorators import login_required, user_passes_test

def is_diretor(user):
    return user.groups.filter(name='Diretoria').exists() or user.is_superuser

def is_professor(user):
    return user.groups.filter(name='Professor').exists()

def is_estagiario(user):
    return user.groups.filter(name='Estagiario').exists()

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def list_condominios(request: HttpRequest):
    # filtros
    q = request.GET.get("q", "").strip()
    cidade = request.GET.get("cidade", "").strip()
    uf = request.GET.get("uf", "").strip().upper()
    ativos_param = request.GET.get("ativos", "")
    if   ativos_param == "1": ativos = True
    elif ativos_param == "0": ativos = False
    else:                     ativos = None

    qs = cs.buscar_condominios(q=q, uf=uf, cidade=cidade, ativos=ativos)

    # paginação segura
    page_str = request.GET.get("page", "1")
    try:
        page = int(page_str)
        if page < 1: page = 1
    except (TypeError, ValueError):
        page = 1
    page_obj = cs.paginar_queryset(qs, page=page, per_page=20)

    # querystring base (remove page)
    qd = request.GET.copy()
    qd.pop("page", None)
    base_qs = qd.urlencode()

    filtro_form = CondominioFiltroForm(initial={
        "q": q, "cidade": cidade, "uf": uf, "ativos": ativos_param
    })
    cond_form = CondominioForm()
    import_form = ImportacaoExcelForm()
    suffix = f"&{base_qs}" if base_qs else ""   # 👈 sufixo pronto

    return render(request, "condominios/list.html", {
        "page_obj": page_obj,
        "filtro_form": filtro_form,
        "cond_form": cond_form,
        "import_form": import_form,
        "UF_CHOICES": UF_CHOICES,
        "q": q, "cidade": cidade, "uf": uf, "ativos_param": ativos_param,
        "base_qs": base_qs,
        "suffix": suffix,                         # 👈 envia pro template
    })

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def create_condominio(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = CondominioForm(request.POST)
    if form.is_valid():
        try:
            cs.criar_condominio(form.cleaned_data)
            messages.success(request, "Condomínio criado com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao criar: {e}")
    else:
        messages.error(request, "Dados inválidos no formulário.")
    return redirect(reverse("condominios:list"))

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def update_condominio(request: HttpRequest, pk: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = CondominioForm(request.POST)
    if form.is_valid():
        try:
            cs.atualizar_condominio(pk, form.cleaned_data)
            messages.success(request, "Condomínio atualizado com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao atualizar: {e}")
    else:
        messages.error(request, "Dados inválidos no formulário.")
    return redirect(reverse("condominios:list"))

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def exportar_condominios_view(request: HttpRequest):
    filename, content = cs.exportar_condominios_para_excel()
    resp = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def importar_condominios_view(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")
    form = ImportacaoExcelForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Envie um arquivo .xlsx válido.")
        return redirect(reverse("condominios:list"))

    try:
        rel = cs.importar_condominios_de_excel(request.FILES["arquivo"])
        messages.success(
            request,
            f"Importação concluída: {rel.get('sucesso',0)} OK, "
            f"{rel.get('criados',0)} criados, {rel.get('atualizados',0)} atualizados. "
            f"{len(rel.get('erros',[]))} erros."
        )
        erros = rel.get("erros", [])
        if erros:
            preview = "; ".join(f"L{e['linha']}: {e['erro']}" for e in erros[:3])
            messages.warning(request, f"Erros (parcial): {preview}")
    except Exception as e:
        messages.error(request, f"Falha na importação: {e}")
    return redirect(reverse("condominios:list"))
