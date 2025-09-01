from __future__ import annotations
from typing import Dict, Any, Optional
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Modalidade

# Exceções de domínio
class ModalidadeJaExiste(ValidationError): ...
class ModalidadeNaoEncontrada(ObjectDoesNotExist): ...

def _nome_existe(nome: str, exclude_id: Optional[int] = None) -> bool:
    qs = Modalidade.objects.filter(nome__iexact=(nome or "").strip())
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()

def paginar_queryset(qs, page: int = 1, per_page: int = 20):
    p = Paginator(qs, per_page)
    try:
        return p.page(page)
    except PageNotAnInteger:
        return p.page(1)
    except EmptyPage:
        return p.page(p.num_pages if page > 1 else 1)

# CRUD
@transaction.atomic
def criar_modalidade(data: Dict[str, Any]) -> Modalidade:
    nome = (data.get("nome") or "").strip()
    if not nome:
        raise ValidationError("Campo 'nome' é obrigatório.")
    if _nome_existe(nome):
        raise ModalidadeJaExiste("Já existe uma modalidade com este nome.")
    obj = Modalidade.objects.create(
        nome=nome,
        descricao=data.get("descricao", "") or "",
        ativo=bool(data.get("ativo", True)),
    )
    return obj

@transaction.atomic
def atualizar_modalidade(modalidade_id: int, data: Dict[str, Any]) -> Modalidade:
    obj = Modalidade.objects.filter(id=modalidade_id).first()
    if not obj:
        raise ModalidadeNaoEncontrada("Modalidade não encontrada.")
    if "nome" in data and data["nome"]:
        novo = (data["nome"] or "").strip()
        if _nome_existe(novo, exclude_id=obj.id):
            raise ModalidadeJaExiste("Já existe uma modalidade com este nome.")
        obj.nome = novo
        # Deixe o slug ser refeito (limpando-o) se quiser que acompanhe renomeações:
        obj.slug = ""  # força regenerar no save()
    for k in ("descricao", "ativo"):
        if k in data:
            setattr(obj, k, data[k] if k != "descricao" else (data[k] or ""))
    obj.full_clean()
    obj.save()
    return obj

def obter_modalidade_por_id(pk: int) -> Modalidade:
    obj = Modalidade.objects.filter(id=pk).first()
    if not obj:
        raise ModalidadeNaoEncontrada("Modalidade não encontrada.")
    return obj

def buscar_modalidades(q: str = "", ativos: Optional[bool] = None):
    qs = Modalidade.objects.all()
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(descricao__icontains=q))
    if ativos is not None:
        qs = qs.filter(ativo=ativos)
    return qs.order_by("nome", "id")

# Seed simples
def criar_exemplos_basicos() -> int:
    base = ["Musculação", "Futebol", "Natação"]
    criados = 0
    for nome in base:
        if not Modalidade.objects.filter(nome__iexact=nome).exists():
            Modalidade.objects.create(nome=nome, ativo=True)
            criados += 1
    return criados
