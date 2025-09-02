# clientes/services.py
from __future__ import annotations
from typing import Optional, Iterable
import re
from datetime import date
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction

from .models import Cliente

_ONLY_DIGITS = re.compile(r"\D+")

def clean_doc(s: str) -> str:
    return _ONLY_DIGITS.sub("", (s or ""))

def paginar(qs, page: int = 1, per_page: int = 20):
    p = Paginator(qs, per_page)
    try:
        return p.page(page)
    except PageNotAnInteger:
        return p.page(1)
    except EmptyPage:
        return p.page(p.num_pages if page > 1 else 1)

def buscar_clientes(q: str = "", ativos: Optional[bool] = None):
    qs = Cliente.objects.all()
    if q:
        q_clean = clean_doc(q)
        cond = Q(nome_razao__icontains=q) | Q(email__icontains=q)
        if q_clean:
            cond |= Q(cpf_cnpj__icontains=q_clean)
        qs = qs.filter(cond)
    if ativos is not None:
        qs = qs.filter(ativo=ativos)
    return qs.order_by("nome_razao", "id")

@transaction.atomic
def criar_cliente(data: dict) -> Cliente:
    data = {**data}
    data["cpf_cnpj"] = clean_doc(data.get("cpf_cnpj", ""))
    if not data["cpf_cnpj"]:
        raise ValidationError("CPF/CNPJ é obrigatório.")
    c = Cliente.objects.create(**data)

    t = enviar_email_aceite(c)
    print(t)
    return c

@transaction.atomic
def atualizar_cliente(cliente_id: int, data: dict) -> Cliente:
    c = Cliente.objects.filter(id=cliente_id).first()
    if not c:
        raise ObjectDoesNotExist("Cliente não encontrado.")
    if "cpf_cnpj" in data:
        data["cpf_cnpj"] = clean_doc(data["cpf_cnpj"])
        if not data["cpf_cnpj"]:
            raise ValidationError("CPF/CNPJ inválido.")
    for k, v in data.items():
        setattr(c, k, v)
    c.full_clean()
    c.save()
    return c

@transaction.atomic
def ativar(cliente_id: int, ativo: bool = True) -> Cliente:
    c = Cliente.objects.filter(id=cliente_id).first()
    if not c:
        raise ObjectDoesNotExist("Cliente não encontrado.")
    c.ativo = bool(ativo)
    c.save(update_fields=["ativo", "updated_at"])
    return c

# ==== Importação/Exportação Excel (openpyxl) ====
def importar_excel(file) -> dict:
    """
    Espera um .xlsx com cabeçalhos:
    cpf_cnpj,nome_razao,data_nascimento,telefone_emergencial,telefone_celular,
    cep,numero_id,logradouro,bairro,complemento,municipio,estado,email,ativo
    """
    from openpyxl import load_workbook
    wb = load_workbook(file, read_only=True, data_only=True)
    ws = wb.active
    headers = [str((c.value or "")).strip() for c in next(ws.rows)]
    idx = {h: i for i, h in enumerate(headers)}
    required = ["cpf_cnpj","nome_razao"]
    for r in required:
        if r not in idx:
            raise ValidationError(f"Coluna obrigatória ausente: {r}")

    created = updated = skipped = 0
    for row in ws.iter_rows(min_row=2):
        get = lambda h: (row[idx[h]].value if h in idx else None)
        data = {
            "cpf_cnpj": clean_doc(str(get("cpf_cnpj") or "")),
            "nome_razao": str(get("nome_razao") or "").strip(),
            "data_nascimento": get("data_nascimento"),
            "telefone_emergencial": str(get("telefone_emergencial") or "").strip(),
            "telefone_celular": str(get("telefone_celular") or "").strip(),
            "cep": str(get("cep") or "").strip(),
            "numero_id": str(get("numero_id") or "").strip(),
            "logradouro": str(get("logradouro") or "").strip(),
            "bairro": str(get("bairro") or "").strip(),
            "complemento": str(get("complemento") or "").strip(),
            "municipio": str(get("municipio") or "").strip(),
            "estado": str(get("estado") or "").strip(),
            "email": str(get("email") or "").strip(),
        }
        ativo_val = get("ativo")
        if ativo_val is not None:
            data["ativo"] = bool(ativo_val in (1, "1", True, "True", "true", "SIM", "Sim", "sim"))

        if not data["cpf_cnpj"] or not data["nome_razao"]:
            skipped += 1
            continue

        # upsert por documento
        obj = Cliente.objects.filter(cpf_cnpj=data["cpf_cnpj"]).first()
        if obj:
            for k, v in data.items():
                setattr(obj, k, v)
            obj.save()
            updated += 1
        else:
            Cliente.objects.create(**data)
            created += 1

    return {"created": created, "updated": updated, "skipped": skipped}

def exportar_excel(queryset=None) -> tuple[str, bytes]:
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    qs = queryset or Cliente.objects.all().order_by("nome_razao","id")

    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    headers = ["CPF/CNPJ","Nome","Nascimento","Celular","Emergencial","CEP","Número","Logradouro","Bairro","Complemento","Município","UF","E-mail","Ativo","ID"]
    ws.append(headers)

    for c in qs:
        ws.append([
            c.cpf_cnpj, c.nome_razao,
            c.data_nascimento.isoformat() if c.data_nascimento else "",
            c.telefone_celular, c.telefone_emergencial,
            c.cep, c.numero_id, c.logradouro, c.bairro, c.complemento, c.municipio, c.estado,
            c.email, "SIM" if c.ativo else "NÃO", c.id
        ])

    for col in range(1, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(col)].width = 20

    bio = BytesIO(); wb.save(bio); bio.seek(0)
    from datetime import datetime
    filename = f"clientes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return filename, bio.read()


# clientes/services.py
from datetime import timedelta
import secrets
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

from .models import Cliente
from notificacoes.emails import send_email_html

def gerar_link_aceite(cliente: Cliente) -> str:
    token = secrets.token_urlsafe(32)
    cliente.contrato_token = token
    cliente.contrato_token_expira_em = timezone.now() + timedelta(days=14)
    cliente.save(update_fields=["contrato_token","contrato_token_expira_em"])
    base = getattr(settings, "SITE_URL", "http://127.0.0.1:8000")
    path = reverse("clientes:aceite", args=[token])
    return f"{base}{path}"

def enviar_email_aceite(cliente: Cliente) -> bool:
    if not cliente.email:
        raise ValueError("Cliente sem e-mail.")
    link = gerar_link_aceite(cliente)
    return send_email_html(
        subject="Confirme seu cadastro — aceite de contrato",
        to=cliente.email,
        template="emails/aceite_contrato.html",
        context={"cliente": cliente, "link_aceite": link},
    )


# clientes/services.py
from django.db.models import Q
from .models import Cliente

def buscar_clientes_api(q: str, limit: int = 15):
    qs = Cliente.objects.filter(ativo=True)
    if q:
        q = q.strip()
        q_clean = "".join(ch for ch in q if ch.isalnum())  # limpa CPF/CNPJ
        qs = qs.filter(
            Q(nome_razao__icontains=q) |
            Q(email__icontains=q) |
            Q(cpf_cnpj__icontains=q_clean)
        )
    return (qs
            .order_by("nome_razao", "id")
            .values("id", "nome_razao", "cpf_cnpj", "email")[:limit])
