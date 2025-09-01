from datetime import date
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest

from .models import Lancamento
from .forms import LancamentoForm, FiltroFinanceiroForm, BaixaForm, RecorrenciaMensalForm
from . import services as fs

@login_required
def list_financeiro(request: HttpRequest):
    f = FiltroFinanceiroForm(request.GET or None)
    cd = f.cleaned_data if f.is_valid() else {}

    qs = fs.buscar_lancamentos(
        q=cd.get("q",""),
        tipo=cd.get("tipo") or None,
        status=cd.get("status") or None,
        venc_de=cd.get("venc_de") or None,
        venc_ate=cd.get("venc_ate") or None,
        cliente_id=cd.get("cliente").id if cd.get("cliente") else None,
        funcionario_id=cd.get("funcionario").id if cd.get("funcionario") else None,
        condominio_id=cd.get("condominio").id if cd.get("condominio") else None,
        turma_id=cd.get("turma").id if cd.get("turma") else None,
        categoria_id=cd.get("categoria").id if cd.get("categoria") else None,
        ativos=(None if (cd.get("ativos") in (None,"")) else (cd.get("ativos") == "1"))
    )

    # paginação segura
    page_str = request.GET.get("page", "1")
    try:
        page = int(page_str); page = 1 if page < 1 else page
    except (TypeError, ValueError):
        page = 1
    page_obj = fs.paginar_queryset(qs, page=page, per_page=20)

    # querystring base sem page
    qd = request.GET.copy(); qd.pop("page", None)
    base_qs = qd.urlencode()
    suffix = f"&{base_qs}" if base_qs else ""

    return render(request, "financeiro/list.html", {
        "filtro_form": f,
        "page_obj": page_obj,
        "suffix": suffix,
        "base_qs": base_qs,
        "lancamento_form": LancamentoForm(),
        "baixa_form": BaixaForm(),
        "recorr_form": RecorrenciaMensalForm(),
    })

@login_required
def create_lancamento(request: HttpRequest):
    if request.method != "POST": return HttpResponseBadRequest("Somente POST.")
    form = LancamentoForm(request.POST)
    if form.is_valid():
        try:
            fs.criar_lancamento(form.cleaned_data)
            messages.success(request, "Lançamento criado.")
        except Exception as e:
            messages.error(request, f"Erro ao criar: {e}")
    else:
        messages.error(request, f"Dados inválidos: {form.errors.as_json()}")
    return redirect(reverse("financeiro:list"))

@login_required
def update_lancamento(request: HttpRequest, pk: int):
    if request.method != "POST": return HttpResponseBadRequest("Somente POST.")
    form = LancamentoForm(request.POST)
    if form.is_valid():
        try:
            fs.atualizar_lancamento(pk, form.cleaned_data)
            messages.success(request, "Lançamento atualizado.")
        except Exception as e:
            messages.error(request, f"Erro ao atualizar: {e}")
    else:
        messages.error(request, f"Dados inválidos: {form.errors.as_json()}")
    return redirect(reverse("financeiro:list"))

@login_required
def cancelar_lancamento_view(request: HttpRequest, pk: int):
    if request.method != "POST": return HttpResponseBadRequest("Somente POST.")
    try:
        fs.cancelar_lancamento(pk)
        messages.success(request, "Lançamento cancelado.")
    except Exception as e:
        messages.error(request, f"Não foi possível cancelar: {e}")
    return redirect(reverse("financeiro:list"))

@login_required
def registrar_baixa_view(request: HttpRequest):
    if request.method != "POST": return HttpResponseBadRequest("Somente POST.")
    form = BaixaForm(request.POST)
    if form.is_valid():
        cd = form.cleaned_data
        try:
            fs.registrar_baixa(
                lancamento_id=cd["lancamento"].id,
                valor=cd["valor"],
                data=cd["data"],
                forma=cd["forma"],
                observacao=cd.get("observacao") or ""
            )
            messages.success(request, "Baixa registrada.")
        except Exception as e:
            messages.error(request, f"Erro ao registrar baixa: {e}")
    else:
        messages.error(request, f"Dados inválidos: {form.errors.as_json()}")
    return redirect(reverse("financeiro:list"))

@login_required
def estornar_baixa_view(request: HttpRequest, baixa_id: int):
    if request.method != "POST": return HttpResponseBadRequest("Somente POST.")
    try:
        fs.estornar_baixa(baixa_id)
        messages.success(request, "Baixa estornada.")
    except Exception as e:
        messages.error(request, f"Não foi possível estornar: {e}")
    return redirect(reverse("financeiro:list"))

@login_required
def gerar_recorrencia_view(request: HttpRequest):
    if request.method != "POST": return HttpResponseBadRequest("Somente POST.")
    form = RecorrenciaMensalForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Dados inválidos: {form.errors.as_json()}")
        return redirect(reverse("financeiro:list"))
    cd = form.cleaned_data
    try:
        rels = {
            "cliente_id": cd["cliente"].id if cd.get("cliente") else None,
            "funcionario_id": cd["funcionario"].id if cd.get("funcionario") else None,
            "condominio_id": cd["condominio"].id if cd.get("condominio") else None,
            "turma_id": cd["turma"].id if cd.get("turma") else None,
        }
        criados = fs.gerar_recorrencia_mensal(
            tipo=cd["tipo"],
            descricao=cd["descricao"],
            valor=cd["valor"],
            dia_venc=cd["dia_venc"],
            quantidade=cd["quantidade"],
            primeiro_mes=cd["primeiro_mes"],
            relacionamentos={k:v for k,v in rels.items() if v},
            categoria_id=cd["categoria"].id if cd.get("categoria") else None,
            observacao=cd.get("observacao") or "",
        )
        messages.success(request, f"Recorrência criada: {criados} lançamento(s).")
    except Exception as e:
        messages.error(request, f"Falha na recorrência: {e}")
    return redirect(reverse("financeiro:list"))

@login_required
def exportar_financeiro_view(request: HttpRequest):
    # Reaproveita filtros
    f = FiltroFinanceiroForm(request.GET or None)
    cd = f.cleaned_data if f.is_valid() else {}
    qs = fs.buscar_lancamentos(
        q=cd.get("q",""),
        tipo=cd.get("tipo") or None,
        status=cd.get("status") or None,
        venc_de=cd.get("venc_de") or None,
        venc_ate=cd.get("venc_ate") or None,
        cliente_id=cd.get("cliente").id if cd.get("cliente") else None,
        funcionario_id=cd.get("funcionario").id if cd.get("funcionario") else None,
        condominio_id=cd.get("condominio").id if cd.get("condominio") else None,
        turma_id=cd.get("turma").id if cd.get("turma") else None,
        categoria_id=cd.get("categoria").id if cd.get("categoria") else None,
        ativos=(None if (cd.get("ativos") in (None,"")) else (cd.get("ativos") == "1"))
    ).select_related("cliente","funcionario","condominio","turma","categoria")

    filename, content = fs.exportar_lancamentos_excel(qs)
    resp = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


from datetime import date
from django.utils.timezone import now
# ...imports existentes...
from . import services as fs

# 👇 acrescente ao arquivo
@login_required
def gerar_mensalidades_view(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Somente POST.")

    comp = request.POST.get("competencia", "").strip()  # formato esperado: YYYY-MM (input type="month")
    dia_str = request.POST.get("dia_venc", "5").strip()
    turma_str = request.POST.get("turma", "").strip()

    # defaults
    today = now().date()
    ano, mes = today.year, today.month

    # parse competência
    try:
        if comp:
            parts = comp.split("-")
            if len(parts) != 2:
                raise ValueError
            ano = int(parts[0])
            mes = int(parts[1])
        dia_venc = max(1, min(31, int(dia_str or "5")))
    except Exception:
        messages.error(request, "Competência inválida. Use o formato AAAA-MM e um dia entre 1 e 31.")
        return redirect(reverse("financeiro:list"))

    try:
        if turma_str:
            rel = fs.gerar_cobrancas_mensalidade_turma(
                turma_id=int(turma_str),
                ano=ano, mes=mes, dia_venc=dia_venc,
            )
            messages.success(
                request,
                f"Mensalidades da turma geradas: {rel['criados']} nova(s), {rel['existentes']} já existia(m). Vencimento: {rel['vencimento'] or '—'}."
            )
        else:
            rel = fs.gerar_cobrancas_mensalidades_global(
                ano=ano, mes=mes, dia_venc=dia_venc,
            )
            messages.success(
                request,
                f"Mensalidades (todas as turmas): {rel['criados']} nova(s), {rel['existentes']} já existia(m)."
            )
    except Exception as e:
        messages.error(request, f"Falha ao gerar mensalidades: {e}")

    return redirect(reverse("financeiro:list"))
