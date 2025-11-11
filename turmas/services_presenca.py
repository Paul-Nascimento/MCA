from __future__ import annotations
from django.shortcuts import get_object_or_404
from typing import Optional, Iterable, Dict
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q, Count, Sum, IntegerField, Case, When
from django.db.models.functions import Coalesce
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .models import Turma, Matricula, ListaPresenca, ItemPresenca


class ListaJaExiste(Exception):
    pass


# ===== Helpers =====

def _matriculas_ativas_na_data(lista: ListaPresenca):
    d = lista.data
    return (
        Matricula.objects
        .select_related("cliente")
        .filter(
            turma=lista.turma,
            ativa=True,
            data_inicio__lte=d
        )
        .filter(Q(data_fim__isnull=True) | Q(data_fim__gte=d))
        .order_by("cliente__nome_razao", "id")
    )

def _snapshots_from_matricula(m: Matricula) -> tuple[str, str]:
    nome = (m.participante_nome or m.cliente.nome_razao or "").strip()
    # ❗ Não existe mais participante_cpf; use outra info ou vazio
    doc  = (m.cliente.cpf_cnpj or "").strip()
    return nome, doc

def _vigente_na_data(turma: Turma, d: date) -> bool:
    if d < turma.inicio_vigencia:
        return False
    if turma.fim_vigencia and d > turma.fim_vigencia:
        return False
    return True


def _weekday_matches(turma: Turma, d: date) -> bool:
    """Checa se o dia da semana de 'd' está marcado nos flags da turma (seg..dom)."""
    return d.weekday() in turma.dias_ativos()


# ===== Consultas =====

def listas_da_turma(turma_id: int, data_de: Optional[date] = None, data_ate: Optional[date] = None):
    """
    Retorna um QuerySet de OBJETOS ListaPresenca, anotados com:
      - total_itens_count
      - total_presentes_count
    (sem usar .values), para compatibilidade com o template e evitando colisão com @property.
    """
    qs = ListaPresenca.objects.filter(turma_id=turma_id)

    if data_de:
        qs = qs.filter(data__gte=data_de)
    if data_ate:
        qs = qs.filter(data__lte=data_ate)

    qs = qs.annotate(
        total_itens_count=Count("itens", distinct=True),
        total_presentes_count=Coalesce(
            Sum(
                Case(
                    When(itens__presente=True, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            0,
        ),
    ).order_by("-data", "-id")

    return qs


def abrir_lista(lista_id: int):
    lista = get_object_or_404(ListaPresenca.objects.select_related("turma", "turma__modalidade", "turma__modalidade__condominio", "turma__professor"), id=lista_id)
    itens = list(
        lista.itens
        .select_related("cliente")
        .order_by("cliente__nome_razao", "id")
    )
    return lista, itens


# ===== Criação/Sincronização =====

@transaction.atomic
def criar_lista_presenca(*, turma_id: int, d: date, observacao_geral: str = "") -> ListaPresenca:
    """
    Cria a lista para a data d, validando:
      - turma ativa
      - data dentro da vigência
      - dia da semana correto (usando flags seg..dom)
      - inexistência de lista duplicada para a data
    E cria itens com snapshot do PARTICIPANTE (se houver) ou do cliente.
    """
    turma = (
        Turma.objects.select_related("modalidade__condominio", "professor")
        .filter(id=turma_id, ativo=True)
        .first()
    )
    if not turma:
        raise ValidationError("Turma não encontrada ou inativa.")
    if not _vigente_na_data(turma, d):
        raise ValidationError("Data fora da vigência da turma.")
    if not _weekday_matches(turma, d):
        raise ValidationError("Data não corresponde a um dia ativo da turma.")

    if ListaPresenca.objects.filter(turma_id=turma_id, data=d).exists():
        raise ListaJaExiste("Já existe lista para esta data.")

    lista = ListaPresenca.objects.create(
        turma=turma,
        data=d,
        observacao_geral=observacao_geral or "",
    )

    # cria itens para as matrículas ativas na data (1 item por MATRÍCULA)
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

        if m.participante_nome:
            ItemPresenca.objects.create(
                lista=lista,
                cliente=m.cliente,
                matricula=None,          # <= sem matrícula para não conflitar na unique_together
                presente=False,
                observacao="",
                cliente_nome_snapshot=m.cliente.nome_razao,
                cliente_doc_snapshot=m.cliente.cpf_cnpj,
            )

    return lista


@transaction.atomic
def sincronizar_itens_lista(lista_id: int) -> None:
    lista = get_object_or_404(ListaPresenca, id=lista_id)

    ativos = list(_matriculas_ativas_na_data(lista))
    ativos_ids = {m.id for m in ativos}

    existentes = list(
        ItemPresenca.objects.filter(lista=lista).select_related("matricula", "cliente")
    )
    by_matricula = {it.matricula_id: it for it in existentes}

    # cria/atualiza itens de matrículas ativas
    for m in ativos:
        it = by_matricula.get(m.id)
        nome_snap, doc_snap = _snapshots_from_matricula(m)
        if it is None:
            ItemPresenca.objects.create(
                lista=lista,
                #turma=lista.turma,
                matricula=m,
                cliente=m.cliente,
                cliente_nome_snapshot=nome_snap,
                cliente_doc_snapshot=doc_snap,
                presente=False,
            )
        else:
            # garante snapshots atualizados
            changed = False
            if it.cliente_nome_snapshot != nome_snap:
                it.cliente_nome_snapshot = nome_snap
                changed = True
            if it.cliente_doc_snapshot != doc_snap:
                it.cliente_doc_snapshot = doc_snap
                changed = True
            if changed:
                it.save(update_fields=["cliente_nome_snapshot", "cliente_doc_snapshot"])

    # remove itens de matrículas que não estão mais ativas no dia
    for it in existentes:
        if it.matricula_id not in ativos_ids:
            it.delete()


# ===== Operações =====

@transaction.atomic
def salvar_presenca(*, lista_id: int, presentes_ids: list[int], obs_por_item: dict[int, str], observacao_geral: str | None, ocorrencia_aula: str | None = None):
    lista = get_object_or_404(ListaPresenca, id=lista_id)
    ids = set(presentes_ids or [])
    for it in lista.itens.all():
        novo_presente = it.id in ids
        new_obs = (obs_por_item.get(it.id) or "").strip()
        updates = []
        if it.presente != novo_presente:
            it.presente = novo_presente
            updates.append("presente")
        if it.observacao != new_obs:
            it.observacao = new_obs
            updates.append("observacao")
        if updates:
            it.save(update_fields=updates)
    if observacao_geral is not None and observacao_geral != (lista.observacao_geral or ""):
        lista.observacao_geral = observacao_geral
        lista.save(update_fields=["observacao_geral"])
    if ocorrencia_aula:
        from .models import OcorrenciaAula
        if lista.ocorrencia_aula != ocorrencia_aula and ocorrencia_aula in dict(OcorrenciaAula.choices):
            lista.ocorrencia_aula = ocorrencia_aula
            lista.save(update_fields=["ocorrencia_aula"])


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
    (usando flags seg..dom) e dentro da vigência. Ignora as que já existirem.
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
