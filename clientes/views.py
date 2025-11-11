# clientes/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone

from .forms import ClienteForm, ClienteFiltroForm
from .models import Cliente
from . import services as cs

from django.contrib.auth.decorators import login_required, user_passes_test

def is_diretor(user):
    return user.groups.filter(name='Diretoria').exists() or user.is_superuser

def is_professor(user):
    return user.groups.filter(name='Professor').exists()

def is_estagiario(user):
    return user.groups.filter(name='Estagiario').exists()

# views.py
UF_LIST = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG",
           "PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"]

@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def list_clientes(request: HttpRequest):
    f = ClienteFiltroForm(request.GET or None)
    cd = f.cleaned_data if f.is_valid() else {}
    qs = cs.buscar_clientes(
        q=cd.get("q", ""),
        ativos=(None if (cd.get("ativos") in (None, "")) else (cd.get("ativos") == "1")),
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
        "uf_list": UF_LIST
    })

@require_http_methods(["POST"])
@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def create_cliente(request: HttpRequest):
    form = ClienteForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Dados inválidos: {form.errors.as_json()}")
        return redirect(reverse("clientes:list"))

    try:
        # criar_cliente já gera token e envia e-mail
        cs.criar_cliente(form.cleaned_data)
        messages.success(request, "Cliente criado e e-mail de aceite enviado.")
    except Exception as e:
        messages.error(request, f"Erro ao criar: {e}")

    return redirect(reverse("clientes:list"))


@require_http_methods(["POST"])
@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def update_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    form = ClienteForm(request.POST, instance=cliente)  # <- AQUI!
    if form.is_valid():
        form.save()  # ou chamar seu service com form.cleaned_data
        messages.success(request, "Cliente atualizado.")
        return redirect("clientes:list")
    messages.error(request, f"Dados inválidos: {form.errors.as_json()}")
    return redirect(f"{reverse('clientes:list')}?edit={pk}")



@require_http_methods(["POST"])
@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def ativar_cliente(request: HttpRequest, pk: int):
    try:
        ativo = request.POST.get("ativo", "1") == "1"
        cs.ativar(pk, ativo=ativo)
        messages.success(request, "Cliente atualizado.")
    except Exception as e:
        messages.error(request, f"Erro: {e}")
    return redirect(reverse("clientes:list"))


@require_http_methods(["POST"])
@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def importar_excel_view(request: HttpRequest):
    f = request.FILES.get("arquivo")
    if not f:
        messages.error(request, "Selecione um arquivo .xlsx")
        return redirect(reverse("clientes:list"))
    try:
        rel = cs.importar_excel(f)
        messages.success(
            request,
            f"Importação: criados={rel.get('created',0)} "
            f"atualizados={rel.get('updated',0)} "
            f"ignorados={rel.get('skipped',0)}"
        )
    except Exception as e:
        messages.error(request, f"Falha ao importar: {e}")
    return redirect(reverse("clientes:list"))


@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def exportar(request: HttpRequest):
    qs = cs.buscar_clientes(
        q=request.GET.get("q", ""),
        ativos=None if request.GET.get("ativos", "") == "" else request.GET.get("ativos") == "1"
    )
    filename, content = cs.exportar_excel(qs)
    resp = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


# --------- Fluxo de aceite (público) ---------
# NÃO usar login_required aqui: o cliente acessa via link de e-mail
@require_http_methods(["GET", "POST"])
def aceite_contrato(request: HttpRequest, token: str):
    # 1) Busca cliente pelo token
    cliente = get_object_or_404(Cliente, aceite_token=token)

    # 2) Valida expiração (ajuste os nomes dos campos conforme seu model)
    if not getattr(cliente, "aceite_expires_at", None) or timezone.now() > cliente.aceite_expires_at:
        messages.error(request, "Link de confirmação expirado. Solicite um novo convite.")
        return render(request, "clientes/aceite_contrato.html", {"expirado": True, "cliente": cliente})

    if request.method == "POST":
        # 3) Confirma aceite
        cliente.ativo = True
        cliente.aceite_confirmado_em = timezone.now()
        # Invalida o token após o uso
        cliente.aceite_token = None
        cliente.aceite_expires_at = None
        cliente.save(update_fields=["ativo", "aceite_confirmado_em", "aceite_token", "aceite_expires_at"])
        # 4) Página de sucesso
        return render(request, "clientes/aceite_sucesso.html", {"cliente": cliente})

    # GET simples mostra a tela de aceite
    return render(request, "clientes/aceite_contrato.html", {"cliente": cliente})


@require_POST
@login_required
@user_passes_test(is_diretor,login_url="/turmas/")
def toggle_status(request, pk: int):
    c = get_object_or_404(Cliente, pk=pk)
    # Se estiver aguardando confirmação (tem token), não permite toggle
    if not c.ativo and getattr(c, "aceite_token", None):
        messages.info(request, "Cliente aguardando confirmação; altere o status somente após a confirmação ou reenviar o convite.")
        return redirect(reverse("clientes:list"))

    c.ativo = not c.ativo
    c.save(update_fields=["ativo"])
    messages.success(request, ("Cliente ativado." if c.ativo else "Cliente desativado."))
    return redirect(reverse("clientes:list"))


# views.py
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages

def _token_valido(cliente):
    return cliente.aceite_token and cliente.aceite_expires_at and timezone.now() <= cliente.aceite_expires_at

def aceite_confirmar(request, token: str):
    cliente = get_object_or_404(Cliente, aceite_token=token)

    if not _token_valido(cliente):
        messages.error(request, "Link de confirmação expirado ou inválido. Solicite um novo convite.")
        return render(request, "clientes/aceite_contrato.html", {"expirado": True, "cliente": cliente})

    # Confirma em 1 clique (GET)
    cliente.ativo = True
    cliente.aceite_confirmado_em = timezone.now()
    cliente.aceite_token = None
    cliente.aceite_expires_at = None
    cliente.save(update_fields=["ativo", "aceite_confirmado_em", "aceite_token", "aceite_expires_at"])

    return render(request, "clientes/aceite_sucesso.html", {"cliente": cliente})
