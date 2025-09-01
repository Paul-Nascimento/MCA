from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import date, timedelta, time, datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Count
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Turma, Matricula

# ========= Exceções de domínio =========
class TurmaConflitoProfessor(ValidationError): ...
class TurmaSemVagas(ValidationError): ...
class TurmaNaoEncontrada(ObjectDoesNotExist): ...
class MatriculaNaoEncontrada(ObjectDoesNotExist): ...
class MatriculaDuplicada(ValidationError): ...

# ========= Helpers =========
def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute

def _intervalos_se_sobrepoem(inicio1: time, dur1: int, inicio2: time, dur2: int) -> bool:
    a1 = _time_to_minutes(inicio1)
    b1 = a1 + int(dur1)
    a2 = _time_to_minutes(inicio2)
    b2 = a2 + int(dur2)
    return a1 < b2 and a2 < b1  # intersecção aberta

def _periodo_sobrepoe(a_ini: date, a_fim: Optional[date], b_ini: date, b_fim: Optional[date]) -> bool:
    a_fim_eff = a_fim or date.max
    b_fim_eff = b_fim or date.max
    return a_ini <= b_fim_eff and b_ini <= a_fim_eff

def paginar_queryset(qs, page: int = 1, per_page: int = 20):
    p = Paginator(qs, per_page)
    try:
        return p.page(page)
    except PageNotAnInteger:
        return p.page(1)
    except EmptyPage:
        return p.page(p.num_pages if page > 1 else 1)

# ========= Regras de negócio =========
def verificar_conflitos_professor(*, professor_id: int, dia_semana: int,
                                  hora_inicio: time, duracao_minutos: int,
                                  inicio_vigencia: date, fim_vigencia: Optional[date],
                                  ignorar_turma_id: Optional[int] = None) -> Optional[Turma]:
    """
    Retorna uma turma conflitante (se existir) na MESMA combinação de (professor, dia_semana)
    com interseção de horário e vigência.
    """
    qs = Turma.objects.filter(
        professor_id=professor_id,
        dia_semana=dia_semana,
    )
    if ignorar_turma_id:
        qs = qs.exclude(id=ignorar_turma_id)
    # filtra vigência que interseque
    qs = qs.filter(
        Q(inicio_vigencia__lte=fim_vigencia or date.max) &
        (Q(fim_vigencia__isnull=True) | Q(fim_vigencia__gte=inicio_vigencia))
    )

    for t in qs:
        if _intervalos_se_sobrepoem(t.hora_inicio, t.duracao_minutos, hora_inicio, duracao_minutos):
            return t
    return None

# REMOVA (ou deixe de usar)
def contar_matriculas_ativas(turma: Turma, na_data: Optional[date] = None) -> int:
    d = na_data or date.today()
    return Matricula.objects.filter(
        turma=turma,
        ativa=True,
    ).filter(
        Q(data_fim__isnull=True) | Q(data_fim__gte=d),
        data_inicio__lte=d
    ).count()


def turma_tem_vaga(turma: Turma) -> bool:
    return contar_matriculas(turma) < turma.capacidade
# ========= CRUD Turma =========
@transaction.atomic
def criar_turma(data: Dict[str, Any]) -> Turma:
    # validações mínimas
    if not data.get("professor_id") or not data.get("modalidade_id") or not data.get("condominio_id"):
        raise ValidationError("Informe professor, modalidade e condomínio.")
    if int(data.get("capacidade", 0)) < 1:
        raise ValidationError("Capacidade deve ser pelo menos 1.")
    if int(data.get("duracao_minutos", 0)) < 1:
        raise ValidationError("Duração inválida.")
    if Decimal(str(data.get("valor", "0"))) < 0:
        raise ValidationError("Valor inválido.")

    conflito = verificar_conflitos_professor(
        professor_id=int(data["professor_id"]),
        dia_semana=int(data["dia_semana"]),
        hora_inicio=data["hora_inicio"],
        duracao_minutos=int(data["duracao_minutos"]),
        inicio_vigencia=data["inicio_vigencia"],
        fim_vigencia=data.get("fim_vigencia"),
    )
    if conflito:
        raise TurmaConflitoProfessor(f"Professor já alocado em '{conflito}' no mesmo horário.")

    t = Turma.objects.create(
        professor_id=int(data["professor_id"]),
        modalidade_id=int(data["modalidade_id"]),
        condominio_id=int(data["condominio_id"]),
        nome_exibicao=data.get("nome_exibicao", "") or "",
        valor=Decimal(str(data["valor"])),
        capacidade=int(data["capacidade"]),
        dia_semana=int(data["dia_semana"]),
        hora_inicio=data["hora_inicio"],
        duracao_minutos=int(data["duracao_minutos"]),
        inicio_vigencia=data["inicio_vigencia"],
        fim_vigencia=data.get("fim_vigencia"),
        ativo=bool(data.get("ativo", True)),
    )
    return t

@transaction.atomic
def atualizar_turma(turma_id: int, data: Dict[str, Any]) -> Turma:
    t = Turma.objects.filter(id=turma_id).first()
    if not t:
        raise TurmaNaoEncontrada("Turma não encontrada.")

    # aplicar alterações num clone lógico
    professor_id = int(data.get("professor_id", t.professor_id))
    dia_semana = int(data.get("dia_semana", t.dia_semana))
    hora_inicio = data.get("hora_inicio", t.hora_inicio)
    duracao = int(data.get("duracao_minutos", t.duracao_minutos))
    inicio_vig = data.get("inicio_vigencia", t.inicio_vigencia)
    fim_vig = data.get("fim_vigencia", t.fim_vigencia)

    conflito = verificar_conflitos_professor(
        professor_id=professor_id,
        dia_semana=dia_semana,
        hora_inicio=hora_inicio,
        duracao_minutos=duracao,
        inicio_vigencia=inicio_vig,
        fim_vigencia=fim_vig,
        ignorar_turma_id=t.id,
    )
    if conflito:
        raise TurmaConflitoProfessor(f"Professor já alocado em '{conflito}' no mesmo horário.")

    # persistir
    for k, v in data.items():
        setattr(t, k, v)
    t.full_clean()
    t.save()
    return t

# ========= Busca =========
def buscar_turmas(
    q: str = "",
    *,
    condominio_id: Optional[int] = None,
    modalidade_id: Optional[int] = None,
    professor_id: Optional[int] = None,
    dia_semana: Optional[int] = None,
    ativos: Optional[bool] = None
):
    qs = Turma.objects.select_related("professor", "modalidade", "condominio").all()
    if q:
        qs = qs.filter(
            Q(nome_exibicao__icontains=q) |
            Q(modalidade__nome__icontains=q) |
            Q(condominio__nome__icontains=q) |
            Q(professor__nome__icontains=q)
        )
    if condominio_id: qs = qs.filter(condominio_id=condominio_id)
    if modalidade_id: qs = qs.filter(modalidade_id=modalidade_id)
    if professor_id:  qs = qs.filter(professor_id=professor_id)
    if dia_semana is not None: qs = qs.filter(dia_semana=dia_semana)
    if ativos is not None: qs = qs.filter(ativo=ativos)
    return qs.order_by("condominio__nome", "modalidade__nome", "dia_semana", "hora_inicio", "id")

# ========= Matrículas =========
@transaction.atomic
def matricular_cliente(*, turma_id: int, cliente_id: int, data_inicio: Optional[date] = None) -> Matricula:
    t = Turma.objects.filter(id=turma_id).first()
    if not t:
        raise TurmaNaoEncontrada("Turma não encontrada.")
    hoje = date.today()
    d_ini = data_inicio or hoje

    # já matriculado ativo?
    # DEPOIS (sem datas; somente 'ativa=True')
    existente = Matricula.objects.filter(
        turma=t, cliente_id=cliente_id, ativa=True
    ).first()
    if existente:
        raise MatriculaDuplicada("Cliente já possui matrícula ativa nesta turma.")

    if not turma_tem_vaga(t):
        raise TurmaSemVagas("Turma sem vagas disponíveis.")


    m = Matricula.objects.create(
        turma=t, cliente_id=cliente_id, data_inicio=d_ini, ativa=True
    )
    return m

@transaction.atomic
def encerrar_matricula(matricula_id: int, quando: Optional[date] = None) -> Matricula:
    m = Matricula.objects.filter(id=matricula_id).first()
    if not m:
        raise MatriculaNaoEncontrada("Matrícula não encontrada.")
    m.ativa = False
    m.data_fim = quando or date.today()
    m.full_clean()
    m.save(update_fields=["ativa", "data_fim"])
    return m


from io import BytesIO
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

# DEPOIS (sem na_data; usa contar_matriculas)
def exportar_turmas_para_excel(queryset=None) -> tuple[str, bytes]:
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    qs = queryset if queryset is not None else Turma.objects.select_related(
        "modalidade","condominio","professor"
    ).all().order_by("condominio__nome","modalidade__nome","dia_semana","hora_inicio","id")

    wb = Workbook()
    ws = wb.active
    ws.title = "Turmas"

    headers = ["Modalidade","Condomínio","Professor","Dia","Hora","Duração(min)","Capacidade","Ocupação","Valor","Início","Fim","Ativa","ID"]
    ws.append(headers)

    for t in qs:
        ocup = contar_matriculas(t)
        ws.append([
            t.modalidade.nome,
            t.condominio.nome,
            t.professor.nome,
            t.get_dia_semana_display(),
            t.hora_inicio.strftime("%H:%M"),
            t.duracao_minutos,
            t.capacidade,
            ocup,
            float(t.valor),
            t.inicio_vigencia.strftime("%Y-%m-%d"),
            t.fim_vigencia.strftime("%Y-%m-%d") if t.fim_vigencia else "",
            bool(t.ativo),
            t.id,
        ])

    for col in range(1, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(col)].width = 22

    from datetime import datetime
    bio = BytesIO(); wb.save(bio); bio.seek(0)
    filename = f"turmas_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return filename, bio.read()




def contar_matriculas(turma: Turma) -> int:
    """Ocupação = total de matrículas ATIVAS (independente de datas)."""
    return Matricula.objects.filter(turma=turma, ativa=True).count()


from typing import Optional, Dict, Any, Iterable
from datetime import date
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .models import Turma, Matricula, ListaPresenca, ItemPresenca

# Exceções específicas
class ListaJaExiste(ValidationError): ...
class ListaNaoEncontrada(ObjectDoesNotExist): ...
class ItemNaoEncontrado(ObjectDoesNotExist): ...

def _matriculas_ativas_na_data(turma: Turma, d: date):
    """
    Matrículas que devem compor a lista: ativas e vigentes na data 'd'.
    """
    return (Matricula.objects
            .filter(turma=turma, ativa=True)
            .filter(Q(data_inicio__lte=d))
            .filter(Q(data_fim__isnull=True) | Q(data_fim__gte=d))
            .select_related("cliente"))

@transaction.atomic
def criar_lista_presenca(*, turma_id: int, d: date, observacao_geral: str = "") -> ListaPresenca:
    turma = Turma.objects.filter(id=turma_id).first()
    if not turma:
        raise ValidationError("Turma não encontrada.")
    # (opcional) validar se a data está dentro da vigência da turma
    if not (turma.inicio_vigencia <= d and (turma.fim_vigencia is None or d <= turma.fim_vigencia)):
        # não bloqueamos, mas você pode decidir bloquear
        pass

    # Garantir unicidade turma+data
    if ListaPresenca.objects.filter(turma=turma, data=d).exists():
        raise ListaJaExiste("Já existe lista de presença para esta turma nesta data.")

    lista = ListaPresenca.objects.create(turma=turma, data=d, observacao_geral=observacao_geral)

    # Popular itens a partir das matrículas vigentes
    itens = []
    for m in _matriculas_ativas_na_data(turma, d):
        itens.append(ItemPresenca(
            lista=lista,
            cliente=m.cliente,
            matricula=m,
            presente=False,
            observacao="",
            cliente_nome_snapshot=m.cliente.nome_razao,
            cliente_doc_snapshot=m.cliente.cpf_cnpj,
        ))
    ItemPresenca.objects.bulk_create(itens)
    return lista

@transaction.atomic
def sincronizar_itens_da_lista(lista_id: int) -> int:
    """
    Garante que todos os alunos vigentes na data da lista estejam nela.
    Não remove itens existentes (preserva histórico e observações).
    Retorna quantos itens foram adicionados.
    """
    lista = ListaPresenca.objects.select_related("turma").filter(id=lista_id).first()
    if not lista:
        raise ListaNaoEncontrada("Lista não encontrada.")
    d = lista.data
    turma = lista.turma

    atuais_ids = set(lista.itens.values_list("cliente_id", flat=True))
    novos = []
    for m in _matriculas_ativas_na_data(turma, d):
        if m.cliente_id not in atuais_ids:
            novos.append(ItemPresenca(
                lista=lista,
                cliente=m.cliente,
                matricula=m,
                presente=False,
                observacao="",
                cliente_nome_snapshot=m.cliente.nome_razao,
                cliente_doc_snapshot=m.cliente.cpf_cnpj,
            ))
    if novos:
        ItemPresenca.objects.bulk_create(novos)
    return len(novos)

@transaction.atomic
def marcar_presenca_item(item_id: int, *, presente: bool, observacao: str = "") -> ItemPresenca:
    item = ItemPresenca.objects.filter(id=item_id).first()
    if not item:
        raise ItemNaoEncontrado("Item de presença não encontrado.")
    item.presente = bool(presente)
    if observacao is not None:
        item.observacao = observacao
    item.save(update_fields=["presente", "observacao", "updated_at"])
    return item

@transaction.atomic
def marcar_presenca_em_lote(lista_id: int, *, presentes: Iterable[int] = (), ausentes: Iterable[int] = (), observacao_padrao: str = "") -> int:
    """
    Marca presença em lote: 'presentes' e 'ausentes' são listas de IDs de ItemPresenca.
    Retorna o total de linhas atualizadas.
    """
    count = 0
    if presentes:
        qs = ItemPresenca.objects.filter(lista_id=lista_id, id__in=list(presentes))
        count += qs.update(presente=True, observacao=observacao_padrao)
    if ausentes:
        qs = ItemPresenca.objects.filter(lista_id=lista_id, id__in=list(ausentes))
        count += qs.update(presente=False, observacao=observacao_padrao)
    return count

def obter_listas_presenca(*, turma_id: Optional[int] = None, data_de: Optional[date] = None, data_ate: Optional[date] = None):
    qs = ListaPresenca.objects.select_related("turma", "turma__modalidade", "turma__condominio", "turma__professor")
    if turma_id:
        qs = qs.filter(turma_id=turma_id)
    if data_de:
        qs = qs.filter(data__gte=data_de)
    if data_ate:
        qs = qs.filter(data__lte=data_ate)
    return qs.order_by("-data", "-id")

def obter_itens_da_lista(lista_id: int):
    return ItemPresenca.objects.select_related("cliente", "matricula").filter(lista_id=lista_id).order_by("cliente_nome_snapshot", "id")

# --- acrescente ao final do arquivo services.py ---
from datetime import timedelta

class NenhumaDataValida(ValidationError): ...

def gerar_listas_automaticas(*, turma_id: int, data_de: date, data_ate: date) -> dict:
    """
    Cria listas de presença para todas as datas entre [data_de, data_ate]
    cujo dia da semana = dia_semana da turma e que estejam dentro da vigência.
    Ignora as que já existirem.
    Retorna: {"criadas": X, "existentes": Y, "ignoradas_fora_vigencia": Z}
    """
    turma = Turma.objects.filter(id=turma_id).first()
    if not turma:
        raise ValidationError("Turma não encontrada.")
    if data_ate < data_de:
        raise ValidationError("Período inválido.")

    criadas = existentes = fora_vig = 0
    d = data_de
    while d <= data_ate:
        if d.weekday() == turma.dia_semana:
            # verifica vigência
            if not (turma.inicio_vigencia <= d and (turma.fim_vigencia is None or d <= turma.fim_vigencia)):
                fora_vig += 1
            else:
                if ListaPresenca.objects.filter(turma=turma, data=d).exists():
                    existentes += 1
                else:
                    criar_lista_presenca(turma_id=turma.id, d=d)  # popula itens
                    criadas += 1
        d += timedelta(days=1)
    return {"criadas": criadas, "existentes": existentes, "ignoradas_fora_vigencia": fora_vig}

# turmas/views_presenca.py (topo do arquivo)
from django.urls import reverse

def _redir_presencas_turma(request, turma_id, error_msg=None):
    """Redireciona de forma segura para a listagem de listas da turma."""
    try:
        tid = int(turma_id)
        return redirect(reverse("turmas:presencas_turma", kwargs={"turma_id": tid}))
    except Exception:
        if error_msg:
            messages.error(request, error_msg)
        return redirect(reverse("turmas:list"))
