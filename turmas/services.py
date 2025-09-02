# turmas/services.py
from __future__ import annotations
from typing import Optional, Iterable, Dict
from datetime import datetime, date, time, timedelta
from decimal import Decimal
import re

from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .models import Turma, Matricula
from clientes.models import Cliente

_ONLY_DIGITS = re.compile(r"\D+")

def _clean_doc(s: str) -> str:
    return _ONLY_DIGITS.sub("", (s or ""))

# =========================
# BUSCA / LISTAGEM DE TURMAS
# =========================
def buscar_turmas(
    *,
    q: str = "",
    condominio_id: Optional[int] = None,
    modalidade_id: Optional[int] = None,
    professor_id: Optional[int] = None,
    dia_semana: Optional[int] = None,
    ativos: Optional[bool] = None,
):
    """
    Retorna queryset de Turma com filtros. Usa select_related para evitar N+1.
    """
    qs = (
        Turma.objects
        .select_related("modalidade", "condominio", "professor")
        .all()
    )

    if q:
        qs = qs.filter(
            Q(nome_exibicao__icontains=q) |
            Q(modalidade__nome__icontains=q) |
            Q(condominio__nome__icontains=q) |
            Q(professor__nome__icontains=q)
        )

    if condominio_id:
        qs = qs.filter(condominio_id=condominio_id)
    if modalidade_id:
        qs = qs.filter(modalidade_id=modalidade_id)
    if professor_id:
        qs = qs.filter(professor_id=professor_id)
    if dia_semana is not None and str(dia_semana) != "":
        qs = qs.filter(dia_semana=dia_semana)
    if ativos is not None:
        qs = qs.filter(ativo=ativos)

    return qs.order_by("modalidade__nome", "condominio__nome", "dia_semana", "hora_inicio", "id")

# =========================
# CRUD DE TURMA
# =========================
def _hora_fim(hora_inicio: time, duracao_minutos: int) -> time:
    dt = datetime.combine(date.today(), hora_inicio) + timedelta(minutes=int(duracao_minutos))
    return dt.time()

def _vigencias_se_cruzam(ini1: date, fim1: Optional[date], ini2: date, fim2: Optional[date]) -> bool:
    fim1x = fim1 or date(2999, 12, 31)
    fim2x = fim2 or date(2999, 12, 31)
    return ini1 <= fim2x and ini2 <= fim1x

def _intervalos_horarios_se_cruzam(h1_ini: time, h1_fim: time, h2_ini: time, h2_fim: time) -> bool:
    # overlap: start < other_end && other_start < end
    return (h1_ini < h2_fim) and (h2_ini < h1_fim)

def _checar_conflito_professor(*, professor_id: int, dia_semana: int,
                               hora_inicio: time, duracao_minutos: int,
                               inicio_vigencia: date, fim_vigencia: Optional[date],
                               turma_id_excluir: Optional[int] = None):
    """
    Impede que o professor tenha duas turmas no mesmo horário/dia com vigência que se cruza.
    """
    h_fim = _hora_fim(hora_inicio, duracao_minutos)
    qs = Turma.objects.filter(
        professor_id=professor_id,
        dia_semana=dia_semana,
        ativo=True
    )
    if turma_id_excluir:
        qs = qs.exclude(id=turma_id_excluir)

    for t in qs.only("id", "hora_inicio", "duracao_minutos", "inicio_vigencia", "fim_vigencia"):
        if not _vigencias_se_cruzam(inicio_vigencia, fim_vigencia, t.inicio_vigencia, t.fim_vigencia):
            continue
        t_fim = _hora_fim(t.hora_inicio, t.duracao_minutos)
        if _intervalos_horarios_se_cruzam(hora_inicio, h_fim, t.hora_inicio, t_fim):
            raise ValidationError(f"Conflito de horário com a turma #{t.id} do mesmo professor.")

@transaction.atomic
def criar_turma(data: dict) -> Turma:
    # Valida conflitos
    _checar_conflito_professor(
        professor_id=data["professor"],
        dia_semana=data["dia_semana"],
        hora_inicio=data["hora_inicio"],
        duracao_minutos=data["duracao_minutos"],
        inicio_vigencia=data["inicio_vigencia"],
        fim_vigencia=data.get("fim_vigencia"),
    )
    t = Turma.objects.create(**data)
    return t

@transaction.atomic
def atualizar_turma(turma_id: int, data: dict) -> Turma:
    t = Turma.objects.filter(id=turma_id).first()
    if not t:
        raise ObjectDoesNotExist("Turma não encontrada.")
    _checar_conflito_professor(
        professor_id=data.get("professor", t.professor_id),
        dia_semana=data.get("dia_semana", t.dia_semana),
        hora_inicio=data.get("hora_inicio", t.hora_inicio),
        duracao_minutos=data.get("duracao_minutos", t.duracao_minutos),
        inicio_vigencia=data.get("inicio_vigencia", t.inicio_vigencia),
        fim_vigencia=data.get("fim_vigencia", t.fim_vigencia),
        turma_id_excluir=t.id
    )
    for k, v in data.items():
        setattr(t, k, v)
    t.full_clean()
    t.save()
    return t

# =========================
# MATRÍCULAS
# =========================
@transaction.atomic
def matricular_cliente(
    *,
    turma_id: int,
    cliente_id: int,
    data_inicio: date,
    participante_nome: str = "",
    participante_cpf: str = "",
    participante_sexo: str = "",
) -> Matricula:
    turma = Turma.objects.filter(id=turma_id, ativo=True).first()
    if not turma:
        raise ValidationError("Turma não encontrada ou inativa.")

    # capacidade
    if hasattr(turma, "ocupacao"):
        # property do model
        if turma.ocupacao >= turma.capacidade:
            raise ValidationError("Turma está lotada.")
    else:
        # fallback
        if Matricula.objects.filter(turma_id=turma_id, ativa=True).count() >= turma.capacidade:
            raise ValidationError("Turma está lotada.")

    # evitar duplicidade do mesmo participante/cliente ativo
    cpf_clean = _clean_doc(participante_cpf)
    dup = Matricula.objects.filter(
        turma_id=turma_id, cliente_id=cliente_id, ativa=True,
        participante_nome=participante_nome.strip(),
        participante_cpf=cpf_clean
    ).exists()
    if dup:
        raise ValidationError("Este participante já está matriculado nesta turma.")

    m = Matricula.objects.create(
        turma_id=turma_id,
        cliente_id=cliente_id,
        data_inicio=data_inicio,
        participante_nome=participante_nome.strip(),
        participante_cpf=cpf_clean,
        participante_sexo=(participante_sexo or "").upper()[:1],
        ativa=True,
    )

    try:
        from notificacoes.emails import send_matricula_resumo
        #send_matricula_resumo(m)
    except Exception as e:
        # opcional: logue isso; por hora, só não interrompe o fluxo
        print("Falha ao enviar e-mail de matrícula:", e)

    return m


@transaction.atomic
def desmatricular(matricula_id: int, data_fim: Optional[date] = None):
    m = Matricula.objects.filter(id=matricula_id, ativa=True).first()
    if not m:
        raise ObjectDoesNotExist("Matrícula não encontrada/ativa.")
    m.ativa = False
    if data_fim:
        m.data_fim = data_fim
    m.save(update_fields=["ativa", "data_fim"])

def alunos_da_turma(turma_id: int):
    """
    Retorna matrículas ativas ordenadas por nome (do participante se houver).
    """
    qs = (
        Matricula.objects
        .select_related("cliente")
        .filter(turma_id=turma_id, ativa=True)
        .order_by("participante_nome", "cliente__nome_razao", "id")
    )
    return qs

# =========================
# EXPORT BÁSICO (opcional)
# =========================
def exportar_turmas_excel(qs=None):
    from openpyxl import Workbook
    from io import BytesIO
    qs = qs or Turma.objects.select_related("modalidade","condominio","professor").all()
    wb = Workbook(); ws = wb.active; ws.title = "Turmas"
    ws.append(["ID","Modalidade","Condomínio","Professor","Dia","Hora","Duração(min)","Capacidade","Valor","Ativa","Vigência Início","Vigência Fim","Nome"])
    for t in qs:
        ws.append([
            t.id, t.modalidade.nome, t.condominio.nome, t.professor.nome,
            t.get_dia_semana_display(), t.hora_inicio.strftime("%H:%M"), t.duracao_minutos,
            t.capacidade, f"{t.valor:.2f}", "SIM" if t.ativo else "NÃO",
            t.inicio_vigencia.isoformat(), t.fim_vigencia.isoformat() if t.fim_vigencia else "",
            t.nome_exibicao or "",
        ])
    bio = BytesIO(); wb.save(bio); bio.seek(0)
    return "turmas.xlsx", bio.read()


# turmas/services.py (substitua a função inteira)

from django.db.models.functions import Coalesce
from django.db.models import Value as V

def alunos_da_turma(turma_id: int):
    """
    Retorna matrículas (ativas) ordenadas pelo nome do participante (se houver) ou do cliente.
    """
    qs = (
        Matricula.objects
        .select_related("cliente")
        .filter(turma_id=turma_id, ativa=True)
        .annotate(
            nome_ord=Coalesce("participante_nome", "cliente__nome_razao"),
            doc_ord=Coalesce("participante_cpf", "cliente__cpf_cnpj"),
        )
        .order_by("nome_ord", "id")
    )
    return qs
