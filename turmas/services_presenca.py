# turmas/services_presenca.py
from __future__ import annotations
from typing import Optional, Iterable, Dict
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q, Count, Sum
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .models import Turma, Matricula, ListaPresenca, ItemPresenca


class ListaJaExiste(Exception):
    pass


# ===== Helpers =====

def _matriculas_ativas_na_data(turma_id: int, d: date):
    """
    Matrículas ativas na data d:
      - data_inicio <= d
      - (data_fim é nula ou >= d)
      - ativa=True
    """
    return (
        Matricula.objects.select_related("cliente")
        .filter(turma_id=turma_id, ativa=True)
        .filter(data_inicio__lte=d)
        .filter(Q(data_fim__isnull=True) | Q(data_fim__gte=d))
        .order_by("cliente__nome_razao", "id")
    )


def _vigente_na_data(turma: Turma, d: date) -> bool:
    if d < turma.inicio_vigencia:
        return False
    if turma.fim_vigencia and d > turma.fim_vigencia:
        return False
    return True


def _weekday_matches(turma: Turma, d: date) -> bool:
    # Monday=0 ... Sunday=6
    return d.weekday() == turma.dia_semana


# ===== Consultas =====

# turmas/services_presenca.py (ou onde estiver)
from typing import Optional
from datetime import date
from django.db.models import Count, Sum, IntegerField, Case, When
from django.db.models.functions import Coalesce
from .models import ListaPresenca

def listas_da_turma(turma_id: int, data_de: Optional[date] = None, data_ate: Optional[date] = None):
    """
    Retorna 'queryset' de dicts com agregados (qtd itens e presentes),
    evitando colisão com propriedades do modelo.
    """
    qs = ListaPresenca.objects.filter(turma_id=turma_id)

    if data_de:
        qs = qs.filter(data__gte=data_de)
    if data_ate:
        qs = qs.filter(data__lte=data_ate)

    qs = (
        qs.annotate(
            total_itens=Count("itens", distinct=True),
            total_presentes=Coalesce(
                Sum(
                    Case(
                        When(itens__presente=True, then=1),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
                0,
            ),
        )
        .values("id", "data", "observacao_geral", "total_itens", "total_presentes")
        .order_by("-data", "-id")
    )
    return qs



def abrir_lista(lista_id: int):
    """
    Carrega a lista + itens ordenados por nome snapshot.
    """
    lista = (
        ListaPresenca.objects
        .select_related("turma", "turma__modalidade", "turma__condominio", "turma__professor")
        .filter(id=lista_id)
        .first()
    )
    if not lista:
        raise ObjectDoesNotExist("Lista não encontrada.")
    itens = (
        ItemPresenca.objects
        .filter(lista=lista)
        .order_by("cliente_nome_snapshot", "id")
    )
    return lista, itens


# ===== Criação/Sincronização =====

@transaction.atomic
def criar_lista_presenca(*, turma_id: int, d: date, observacao_geral: str = "") -> ListaPresenca:
    """
    Cria a lista para a data d, validando:
      - turma ativa
      - data dentro da vigência
      - dia da semana correto
      - inexistência de lista duplicada para a data
    E cria itens com snapshot do PARTICIPANTE (se houver) ou do cliente.
    """
    turma = (
        Turma.objects.select_related("modalidade", "condominio", "professor")
        .filter(id=turma_id, ativo=True)
        .first()
    )
    if not turma:
        raise ValidationError("Turma não encontrada ou inativa.")
    if not _vigente_na_data(turma, d):
        raise ValidationError("Data fora da vigência da turma.")
    if not _weekday_matches(turma, d):
        raise ValidationError("Data não corresponde ao dia da semana da turma.")

    if ListaPresenca.objects.filter(turma_id=turma_id, data=d).exists():
        raise ListaJaExiste("Já existe lista para esta data.")

    lista = ListaPresenca.objects.create(
        turma=turma,
        data=d,
        observacao_geral=observacao_geral or "",
    )

    # cria itens para as matrículas ativas na data
    for m in _matriculas_ativas_na_data(turma_id, d):
        nome_snap = (m.participante_nome or m.cliente.nome_razao).strip()
        doc_snap = (m.participante_cpf or m.cliente.cpf_cnpj)
        ItemPresenca.objects.create(
            lista=lista,
            cliente=m.cliente,
            matricula=m,
            presente=False,
            observacao="",
            cliente_nome_snapshot=nome_snap,
            cliente_doc_snapshot=doc_snap,
        )

    return lista


@transaction.atomic
def sincronizar_itens_lista(lista_id: int) -> Dict[str, int]:
    """
    Garante que a lista tenha itens para TODAS as matrículas ativas na data da lista.
    - Adiciona itens faltantes.
    - Não remove itens existentes (mantém histórico manual).
    Retorna {"adicionados": X, "existentes": Y}.
    """
    lista = ListaPresenca.objects.select_related("turma").filter(id=lista_id).first()
    if not lista:
        raise ObjectDoesNotExist("Lista não encontrada.")

    d = lista.data
    turma_id = lista.turma_id

    atuais = {
        it.matricula_id
        for it in ItemPresenca.objects.filter(lista=lista).only("matricula_id")
    }
    adicionados = existentes = 0

    for m in _matriculas_ativas_na_data(turma_id, d):
        if m.id in atuais:
            existentes += 1
            continue
        nome_snap = (m.participante_nome or m.cliente.nome_razao).strip()
        doc_snap = (m.participante_cpf or m.cliente.cpf_cnpj)
        ItemPresenca.objects.create(
            lista=lista,
            cliente=m.cliente,
            matricula=m,
            presente=False,
            observacao="",
            cliente_nome_snapshot=nome_snap,
            cliente_doc_snapshot=doc_snap,
        )
        adicionados += 1

    return {"adicionados": adicionados, "existentes": existentes}


# ===== Operações =====

@transaction.atomic
def salvar_presenca(
    *,
    lista_id: int,
    presentes_ids: Optional[Iterable[int]],
    obs_por_item: Optional[Dict[int, str]],
    observacao_geral: str = "",
) -> bool:
    """
    Salva marcações de presença e observações por item, além de observação geral.
    """
    lista = ListaPresenca.objects.filter(id=lista_id).first()
    if not lista:
        raise ObjectDoesNotExist("Lista não encontrada.")

    presentes_set = set(int(x) for x in (presentes_ids or []))

    itens = ItemPresenca.objects.filter(lista_id=lista_id)
    for it in itens:
        novo_valor = it.id in presentes_set
        fields = []
        if it.presente != novo_valor:
            it.presente = novo_valor
            fields.append("presente")
        if obs_por_item and it.id in obs_por_item:
            nova_obs = (obs_por_item[it.id] or "").strip()
            if nova_obs != (it.observacao or ""):
                it.observacao = nova_obs
                fields.append("observacao")
        if fields:
            it.save(update_fields=fields + ["updated_at"])

    if (observacao_geral or "") != (lista.observacao_geral or ""):
        lista.observacao_geral = observacao_geral or ""
        lista.save(update_fields=["observacao_geral", "updated_at"])

    return True


# ===== Geração automática =====

@transaction.atomic
def gerar_listas_automaticas(
    *,
    turma_id: int,
    data_de: date,
    data_ate: date,
) -> Dict[str, int]:
    """
    Gera listas entre [data_de, data_ate] apenas nos dias que batem com a turma
    e dentro da vigência. Ignora as que já existirem.
    """
    turma = Turma.objects.filter(id=turma_id, ativo=True).first()
    if not turma:
        raise ValidationError("Turma não encontrada ou inativa.")
    if data_ate < data_de:
        raise ValidationError("Período inválido.")

    criadas = existentes = ignoradas = 0

    d = data_de
    while d <= data_ate:
        try:
            if _vigente_na_data(turma, d) and _weekday_matches(turma, d):
                if ListaPresenca.objects.filter(turma_id=turma_id, data=d).exists():
                    existentes += 1
                else:
                    criar_lista_presenca(turma_id=turma_id, d=d, observacao_geral="")
                    criadas += 1
            else:
                ignoradas += 1
        except ListaJaExiste:
            existentes += 1
        d += timedelta(days=1)

    return {"criadas": criadas, "existentes": existentes, "ignoradas_fora_vigencia": ignoradas}
