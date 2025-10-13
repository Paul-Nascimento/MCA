from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Dict, Optional, Tuple, List, Any

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q, QuerySet

from .models import Turma

# Imports opcionais — só são usados em funções específicas.
# Mantidos dentro das funções quando possível para evitar carregamento antecipado.
try:
    from clientes.models import Cliente  # noqa
except Exception:
    Cliente = None  # apenas para type hints/robustez

# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------

# Mapa para filtro de "dia_semana" (1..7)
_DIA_FIELD = {1: "seg", 2: "ter", 3: "qua", 4: "qui", 5: "sex", 6: "sab", 7: "dom"}

def _dias_ativos_from_obj(t: Turma) -> List[str]:
    out = []
    if t.seg: out.append("Seg")
    if t.ter: out.append("Ter")
    if t.qua: out.append("Qua")
    if t.qui: out.append("Qui")
    if t.sex: out.append("Sex")
    if t.sab: out.append("Sáb")
    if t.dom: out.append("Dom")
    return out

def _flags_from_data(data: Dict[str, Any], fallback: Optional[Turma] = None) -> Dict[str, bool]:
    def getb(k: str) -> bool:
        if k in data:
            v = data[k]
            if isinstance(v, bool):
                return v
            return str(v).lower() in ("1", "true", "on")
        return bool(getattr(fallback, k)) if fallback is not None else False
    return {k: getb(k) for k in ("seg", "ter", "qua", "qui", "sex", "sab", "dom")}

def _qtd_dias(flags: Dict[str, bool]) -> int:
    return sum(1 for v in flags.values() if v)

def _hora_cruza(hini: time, dur: int, hini_b: time, dur_b: int) -> bool:
    a0, a1 = hini.hour * 60 + hini.minute, hini.hour * 60 + hini.minute + int(dur)
    b0, b1 = hini_b.hour * 60 + hini_b.minute, hini_b.hour * 60 + hini.minute + int(dur_b)
    # corrigindo b1 (typo acima): use hini_b
    b0, b1 = hini_b.hour * 60 + hini_b.minute, hini_b.hour * 60 + hini_b.minute + int(dur_b)
    return (a0 < b1) and (b0 < a1)

# ------------------------------------------------------------
# Regras/validações de conflito
# ------------------------------------------------------------

def _checar_conflito_professor(
    *,
    professor_id: int,
    flags: Dict[str, bool],
    hora_inicio: time,
    duracao_minutos: int,
    inicio_vigencia: date,
    fim_vigencia: Optional[date],
    turma_id_excluir: Optional[int] = None,
):
    if _qtd_dias(flags) == 0:
        raise ValidationError("Selecione ao menos um dia da semana.")

    qs = Turma.objects.filter(professor_id=professor_id)
    if turma_id_excluir:
        qs = qs.exclude(id=turma_id_excluir)

    # filtra dias ativos
    dia_q = Q()
    for k, ativo in flags.items():
        if ativo:
            dia_q |= Q(**{k: True})
    if dia_q:
        qs = qs.filter(dia_q)

    # filtra vigência que cruza
    qs = qs.filter(
        Q(fim_vigencia__isnull=True, inicio_vigencia__lte=fim_vigencia or date.max) |
        Q(fim_vigencia__isnull=False, inicio_vigencia__lte=fim_vigencia or date.max, fim_vigencia__gte=inicio_vigencia)
    )

    # checa choque de horário
    for t in qs.only("id", "hora_inicio", "duracao_minutos"):
        if _hora_cruza(hora_inicio, duracao_minutos, t.hora_inicio, t.duracao_minutos):
            raise ValidationError("Conflito de horário para o professor em pelo menos um dos dias selecionados.")

# ------------------------------------------------------------
# CRUD Turmas
# ------------------------------------------------------------

@transaction.atomic
def criar_turma(data: Dict[str, Any]) -> Turma:
    """
    Recebe TurmaForm.cleaned_data. FKs são instâncias (professor, modalidade).
    """
    flags = _flags_from_data(data)

    prof = data["professor"]
    professor_id = prof.id if hasattr(prof, "id") else int(prof)

    _checar_conflito_professor(
        professor_id=professor_id,
        flags=flags,
        hora_inicio=data["hora_inicio"],
        duracao_minutos=int(data["duracao_minutos"]),
        inicio_vigencia=data["inicio_vigencia"],
        fim_vigencia=data.get("fim_vigencia"),
    )

    if data.get("fim_vigencia") and data["fim_vigencia"] < data["inicio_vigencia"]:
        raise ValidationError("A data de fim da vigência não pode ser anterior ao início.")

    return Turma.objects.create(**data)

@transaction.atomic
def atualizar_turma(turma_id: int, data: Dict[str, Any]) -> Turma:
    t = Turma.objects.filter(id=turma_id).first()
    if not t:
        raise ObjectDoesNotExist("Turma não encontrada.")

    flags = _flags_from_data(data, fallback=t)

    prof_or_id = data.get("professor", t.professor_id)
    professor_id = prof_or_id.id if hasattr(prof_or_id, "id") else int(prof_or_id)

    _checar_conflito_professor(
        professor_id=professor_id,
        flags=flags,
        hora_inicio=data.get("hora_inicio", t.hora_inicio),
        duracao_minutos=int(data.get("duracao_minutos", t.duracao_minutos)),
        inicio_vigencia=data.get("inicio_vigencia", t.inicio_vigencia),
        fim_vigencia=data.get("fim_vigencia", t.fim_vigencia),
        turma_id_excluir=t.id,
    )

    for k, v in data.items():
        setattr(t, k, v)

    if t.fim_vigencia and t.fim_vigencia < t.inicio_vigencia:
        raise ValidationError("A data de fim da vigência não pode ser anterior ao início.")

    t.full_clean()
    t.save()
    return t

@transaction.atomic
def toggle_status(turma_id: int) -> Turma:
    t = Turma.objects.filter(id=turma_id).first()
    if not t:
        raise ObjectDoesNotExist("Turma não encontrada.")
    t.ativo = not bool(t.ativo)
    t.save(update_fields=["ativo"])
    return t

# ------------------------------------------------------------
# Matrículas
# ------------------------------------------------------------
@transaction.atomic
def matricular_cliente(
    *,
    turma_id: int,
    cliente_id: int,
    data_inicio: date,
    participante_nome: str = "",
    participante_cpf: str = "",
    participante_sexo: str = "",
    proprio_cliente: bool = True
):
    """
    Cria uma matrícula. Quando é o próprio cliente, os campos de participante
    devem ir como string vazia (""), não None, para não violar NOT NULL.
    """
    try:
        from .models import Matricula
    except Exception as e:
        raise ValidationError("Matrícula indisponível neste projeto.") from e

    if not cliente_id:
        raise ValidationError("Cliente é obrigatório.")

    # Normaliza campos para respeitar NOT NULL no banco
    if proprio_cliente:
        p_nome = ""
        p_cpf  = ""
        p_sexo = ""
    else:
        p_nome = (participante_nome or "").strip()
        p_cpf  = (participante_cpf or "").strip()
        p_sexo = (participante_sexo or "").strip()

    obj = Matricula.objects.create(
        turma_id=turma_id,
        cliente_id=cliente_id,
        data_inicio=data_inicio,
        ativa=True,
        participante_nome=p_nome,
        participante_cpf=p_cpf,
        participante_sexo=p_sexo,
    )
    return obj


@transaction.atomic
def desmatricular(matricula_id: int):
    try:
        from .models import Matricula
    except Exception as e:
        raise ValidationError("Desmatrícula indisponível neste projeto.") from e

    m = Matricula.objects.filter(id=matricula_id).first()
    if not m:
        raise ObjectDoesNotExist("Matrícula não encontrada.")
    m.ativa = False
    m.save(update_fields=["ativa"])
    return m

# ------------------------------------------------------------
# Busca / Exportação
# ------------------------------------------------------------

def buscar_turmas(
    *,
    q: str = "",
    condominio_id: Optional[int] = None,
    modalidade_id: Optional[int] = None,
    professor_id: Optional[int] = None,
    dia_semana: Optional[int] = None,  # 1..7
    ativos: Optional[bool] = None,
) -> QuerySet[Turma]:
    """
    Agora condominio vem de modalidade. Mantemos filtro por condominio (via modalidade__condominio_id).
    """
    qs = Turma.objects.select_related("modalidade__condominio", "professor").all()

    if q:
        qs = qs.filter(
            Q(nome_exibicao__icontains=q) |
            Q(modalidade__nome__icontains=q) |
            Q(modalidade__condominio__nome__icontains=q) |
            Q(professor__nome__icontains=q)
        )

    if condominio_id:
        qs = qs.filter(modalidade__condominio_id=condominio_id)

    if modalidade_id:
        qs = qs.filter(modalidade_id=modalidade_id)

    if professor_id:
        qs = qs.filter(professor_id=professor_id)

    if dia_semana not in (None, ""):
        try:
            field = _DIA_FIELD[int(dia_semana)]
            qs = qs.filter(**{field: True})
        except Exception:
            pass

    if ativos is not None:
        qs = qs.filter(ativo=bool(ativos))

    return qs.order_by("modalidade__condominio__nome", "modalidade__nome", "hora_inicio", "id")

def exportar_turmas_excel(qs: Optional[QuerySet[Turma]] = None) -> Tuple[str, bytes]:
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    from datetime import datetime

    qs = qs or Turma.objects.select_related("modalidade__condominio", "professor").all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Turmas"

    headers = [
        "ID", "Modalidade", "Condomínio", "Professor", "Dias", "Hora Início",
        "Duração (min)", "Capacidade", "Valor", "Ativa", "Início Vigência", "Fim Vigência", "Nome Exibição"
    ]
    ws.append(headers)

    for t in qs:
        dias = ", ".join(_dias_ativos_from_obj(t)) or "—"
        ws.append([
            t.id,
            getattr(t.modalidade, "nome", ""),
            getattr(getattr(t.modalidade, "condominio", None), "nome", ""),
            getattr(t.professor, "nome", ""),
            dias,
            t.hora_inicio.strftime("%H:%M"),
            t.duracao_minutos,
            t.capacidade,
            f"{getattr(t, 'valor', Decimal('0.00')):.2f}",
            "SIM" if t.ativo else "NÃO",
            t.inicio_vigencia.isoformat(),
            t.fim_vigencia.isoformat() if t.fim_vigencia else "",
            t.nome_exibicao or "",
        ])

    for col in range(1, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(col)].width = 22

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    filename = f"turmas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return filename, bio.read()
