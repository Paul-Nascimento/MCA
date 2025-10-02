from __future__ import annotations
from typing import Dict, Any, Optional
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Modalidade
from condominios.models import Condominio

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


# ADICIONE: helper para normalizar id de condomínio
def _norm_condominio_id(val) -> Optional[int]:
    if isinstance(val, Condominio):
        return val.id
    if val in (None, ""):
        return None
    # strings do form GET/POST
    try:
        return int(val)
    except (TypeError, ValueError):
        raise ValidationError("Condomínio inválido.")

def _nome_existe_no_condominio(nome: str, condominio_id: int, exclude_id: Optional[int] = None) -> bool:
    qs = Modalidade.objects.filter(
        nome__iexact=(nome or "").strip(),
        condominio_id=condominio_id,
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()


@transaction.atomic
def criar_modalidade(data: Dict[str, Any]) -> Modalidade:
    nome = (data.get("nome") or "").strip()
    descricao = (data.get("descricao") or "")
    ativo = bool(data.get("ativo", True))

    # ⚠️ AQUI: aceitar tanto instância quanto id/str
    condominio_id = _norm_condominio_id(data.get("condominio") or data.get("condominio_id"))
    if not condominio_id:
        raise ValidationError("Condomínio é obrigatório.")

    if _nome_existe_no_condominio(nome, condominio_id):
        raise ModalidadeJaExiste("Já existe uma modalidade com este nome neste condomínio.")

    obj = Modalidade.objects.create(
        nome=nome,
        descricao=descricao,
        ativo=ativo,
        condominio_id=condominio_id,  # agora é int
    )
    obj.full_clean()
    obj.save()
    return obj


@transaction.atomic
def atualizar_modalidade(pk: int, data: Dict[str, Any]) -> Modalidade:
    obj = Modalidade.objects.filter(id=pk).first()
    if not obj:
        raise ModalidadeNaoEncontrada("Modalidade não encontrada.")

    novo_nome = (data.get("nome", obj.nome) or "").strip()
    novo_descricao = data.get("descricao", obj.descricao) or ""
    novo_ativo = bool(data.get("ativo", obj.ativo))
    # ⚠️ idem aqui
    novo_condominio_id = _norm_condominio_id(
        data.get("condominio") or data.get("condominio_id") or obj.condominio_id
    )

    if _nome_existe_no_condominio(novo_nome, novo_condominio_id, exclude_id=obj.id):
        raise ModalidadeJaExiste("Já existe uma modalidade com este nome neste condomínio.")

    obj.nome = novo_nome
    obj.descricao = novo_descricao
    obj.ativo = novo_ativo
    obj.condominio_id = novo_condominio_id
    obj.slug = ""  # se quiser recriar slug quando renomeia
    obj.full_clean()
    obj.save()
    return obj


def obter_modalidade_por_id(pk: int) -> Modalidade:
    obj = Modalidade.objects.filter(id=pk).first()
    if not obj:
        raise ModalidadeNaoEncontrada("Modalidade não encontrada.")
    return obj


def buscar_modalidades(q: str = "", ativos: Optional[bool] = None, condominio: Optional[int] = None):
    qs = Modalidade.objects.all().select_related("condominio")
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(descricao__icontains=q))
    if ativos is not None:
        qs = qs.filter(ativo=ativos)
    # ⚠️ condominio pode vir str do GET
    condominio_id = _norm_condominio_id(condominio)
    if condominio_id:
        qs = qs.filter(condominio_id=condominio_id)
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
