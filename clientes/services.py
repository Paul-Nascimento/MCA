# apps/clientes/services.py
from __future__ import annotations
from typing import Iterable, Optional, Tuple, Dict, Any, List
from datetime import date

from django.db import transaction
from django.core.paginator import Paginator, Page
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .models import Cliente, VinculoCliente
from django.db.models import Q


# =========================
#   Exceções de domínio
# =========================
class ClienteJaExiste(ValidationError):
    pass

class ClienteNaoEncontrado(ObjectDoesNotExist):
    pass

class VinculoInvalido(ValidationError):
    pass


# =========================
#   Helpers utilitários
# =========================
def _clean_doc(value: str) -> str:
    """
    Normaliza CPF/CNPJ removendo tudo que não é dígito.
    """
    if not value:
        return value
    return ''.join(ch for ch in str(value) if ch.isdigit())


def _assert_cliente_existe(cliente: Optional[Cliente], msg="Cliente não encontrado"):
    if cliente is None:
        raise ClienteNaoEncontrado(msg)


# =========================
#   CRUD Cliente
# =========================
@transaction.atomic
def criar_cliente(data: Dict[str, Any]) -> Cliente:
    """
    Cria cliente garantindo unicidade de CPF/CNPJ.
    Campos aceitos:
      - cpf_cnpj, nome_razao, data_nascimento,
        telefone_emergencial, telefone_celular, email,
        cep, numero_id, logradouro, bairro, complemento, municipio, estado,
        ativo (bool)
    """
    if "cpf_cnpj" not in data:
        raise ValidationError("Campo 'cpf_cnpj' é obrigatório.")

    data = {**data}
    data["cpf_cnpj"] = _clean_doc(data["cpf_cnpj"])

    if Cliente.objects.filter(cpf_cnpj=data["cpf_cnpj"]).exists():
        raise ClienteJaExiste("Já existe cliente com este CPF/CNPJ.")

    cliente = Cliente.objects.create(**data)
    return cliente


@transaction.atomic
def atualizar_cliente(cliente_id: int, data: Dict[str, Any]) -> Cliente:
    """
    Atualiza dados cadastrais. Se mudar cpf_cnpj, valida unicidade.
    """
    cliente = Cliente.objects.filter(id=cliente_id).first()
    _assert_cliente_existe(cliente)

    if "cpf_cnpj" in data and data["cpf_cnpj"]:
        novo_doc = _clean_doc(data["cpf_cnpj"])
        if Cliente.objects.exclude(id=cliente_id).filter(cpf_cnpj=novo_doc).exists():
            raise ClienteJaExiste("Já existe cliente com este CPF/CNPJ.")
        data["cpf_cnpj"] = novo_doc

    for campo, valor in data.items():
        setattr(cliente, campo, valor)

    cliente.full_clean()
    cliente.save()
    return cliente


@transaction.atomic
def inativar_cliente(cliente_id: int) -> Cliente:
    cliente = Cliente.objects.filter(id=cliente_id).first()
    _assert_cliente_existe(cliente)
    cliente.ativo = False
    cliente.save(update_fields=["ativo"])
    return cliente


@transaction.atomic
def reativar_cliente(cliente_id: int) -> Cliente:
    cliente = Cliente.objects.filter(id=cliente_id).first()
    _assert_cliente_existe(cliente)
    cliente.ativo = True
    cliente.save(update_fields=["ativo"])
    return cliente


def obter_cliente_por_id(cliente_id: int) -> Cliente:
    cliente = Cliente.objects.filter(id=cliente_id).first()
    _assert_cliente_existe(cliente)
    return cliente


def obter_cliente_por_cpf_cnpj(cpf_cnpj: str) -> Cliente:
    doc = _clean_doc(cpf_cnpj)
    cliente = Cliente.objects.filter(cpf_cnpj=doc).first()
    _assert_cliente_existe(cliente)
    return cliente


def buscar_clientes(q: str = "", ativos: Optional[bool] = None):
    qs = Cliente.objects.all()
    if q:
        q_clean = _clean_doc(q)
        qs = qs.filter(
            Q(nome_razao__icontains=q) |
            Q(email__icontains=q) |
            Q(cpf_cnpj__icontains=q_clean)
        )
    if ativos is not None:
        qs = qs.filter(ativo=ativos)
    # ordem determinística ajuda a paginação
    return qs.order_by("nome_razao", "id")


def paginar_queryset(qs, page: int = 1, per_page: int = 20) -> Page:
    paginator = Paginator(qs, per_page)
    return paginator.get_page(page)


# =========================
#   Endereço / contato
# =========================
@transaction.atomic
def atualizar_endereco(
    cliente_id: int,
    *,
    cep: Optional[str] = None,
    numero_id: Optional[str] = None,
    logradouro: Optional[str] = None,
    bairro: Optional[str] = None,
    complemento: Optional[str] = None,
    municipio: Optional[str] = None,
    estado: Optional[str] = None,
) -> Cliente:
    cliente = obter_cliente_por_id(cliente_id)
    if cep is not None: cliente.cep = cep
    if numero_id is not None: cliente.numero_id = numero_id
    if logradouro is not None: cliente.logradouro = logradouro
    if bairro is not None: cliente.bairro = bairro
    if complemento is not None: cliente.complemento = complemento
    if municipio is not None: cliente.municipio = municipio
    if estado is not None: cliente.estado = estado
    cliente.full_clean()
    cliente.save()
    return cliente


@transaction.atomic
def atualizar_contato(
    cliente_id: int,
    *,
    telefone_emergencial: Optional[str] = None,
    telefone_celular: Optional[str] = None,
    email: Optional[str] = None,
) -> Cliente:
    cliente = obter_cliente_por_id(cliente_id)
    if telefone_emergencial is not None: cliente.telefone_emergencial = telefone_emergencial
    if telefone_celular is not None: cliente.telefone_celular = telefone_celular
    if email is not None: cliente.email = email
    cliente.full_clean()
    cliente.save()
    return cliente


# =========================
#   Vínculos R ↔ D
# =========================
def listar_dependentes(responsavel_id: int):
    responsavel = obter_cliente_por_id(responsavel_id)
    return responsavel.dependentes


def listar_responsaveis(dependente_id: int):
    dependente = obter_cliente_por_id(dependente_id)
    return dependente.responsaveis


@transaction.atomic
def vincular_responsavel_dependente(
    responsavel_id: int,
    dependente_id: int,
    *,
    tipo: str = "OUTRO",
    inicio: Optional[date] = None,
    fim: Optional[date] = None,
    observacoes: str = ""
) -> VinculoCliente:
    """
    Cria um vínculo R -> D. Evita auto-vínculo e duplicidade por (responsavel, dependente, tipo).
    """
    if responsavel_id == dependente_id:
        raise VinculoInvalido("Um cliente não pode ser responsável de si mesmo.")

    responsavel = obter_cliente_por_id(responsavel_id)
    dependente = obter_cliente_por_id(dependente_id)

    vinculo, created = VinculoCliente.objects.get_or_create(
        responsavel=responsavel,
        dependente=dependente,
        tipo=tipo,
        defaults={"inicio": inicio, "fim": fim, "observacoes": observacoes, "papel": "RESPONSAVEL"},
    )
    if not created:
        # Atualiza campos mutáveis (ex.: datas/observações)
        changed = False
        for field, value in {"inicio": inicio, "fim": fim, "observacoes": observacoes}.items():
            if value is not None and getattr(vinculo, field) != value:
                setattr(vinculo, field, value)
                changed = True
        if changed:
            vinculo.full_clean()
            vinculo.save()
    return vinculo


@transaction.atomic
def encerrar_vinculo(vinculo_id: int, data_fim: Optional[date] = None) -> VinculoCliente:
    vinculo = VinculoCliente.objects.filter(id=vinculo_id).first()
    if not vinculo:
        raise VinculoInvalido("Vínculo não encontrado.")
    vinculo.fim = data_fim or date.today()
    vinculo.full_clean()
    vinculo.save(update_fields=["fim"])
    return vinculo


@transaction.atomic
def remover_vinculo(vinculo_id: int) -> None:
    vinculo = VinculoCliente.objects.filter(id=vinculo_id).first()
    if not vinculo:
        raise VinculoInvalido("Vínculo não encontrado.")
    vinculo.delete()


@transaction.atomic
def substituir_responsavel(
    dependente_id: int,
    antigo_responsavel_id: int,
    novo_responsavel_id: int,
    *,
    tipo: str = "OUTRO",
    manter_historico: bool = True
) -> VinculoCliente:
    """
    Troca o responsável em um determinado tipo de vínculo.
    - manter_historico=True encerra o vínculo antigo e cria um novo
    - manter_historico=False deleta o antigo e cria o novo
    """
    if novo_responsavel_id == antigo_responsavel_id:
        raise VinculoInvalido("Responsável novo é o mesmo que o antigo.")

    # encerra/remove vínculo atual
    vinculo_antigo = VinculoCliente.objects.filter(
        responsavel_id=antigo_responsavel_id,
        dependente_id=dependente_id,
        tipo=tipo
    ).first()

    if not vinculo_antigo:
        raise VinculoInvalido("Vínculo antigo não encontrado para este dependente/tipo.")

    if manter_historico:
        encerrar_vinculo(vinculo_antigo.id)
    else:
        vinculo_antigo.delete()

    # cria o novo
    return vincular_responsavel_dependente(
        responsavel_id=novo_responsavel_id,
        dependente_id=dependente_id,
        tipo=tipo,
        inicio=date.today()
    )


def obter_arvore_dependentes(responsavel_id: int, profundidade: int = 3) -> Dict[str, Any]:
    """
    Retorna uma estrutura de árvore (até N níveis) de dependentes.
    Ex.: {"id": 1, "nome": "...", "filhos": [ ... ]}
    """
    responsavel = obter_cliente_por_id(responsavel_id)

    def _node(cli: Cliente, depth: int) -> Dict[str, Any]:
        if depth <= 0:
            return {"id": cli.id, "nome": cli.nome_razao, "cpf_cnpj": cli.cpf_cnpj, "filhos": []}
        filhos = [
            _node(dep, depth - 1)
            for dep in cli.dependentes.all().order_by("nome_razao")
        ]
        return {"id": cli.id, "nome": cli.nome_razao, "cpf_cnpj": cli.cpf_cnpj, "filhos": filhos}

    return _node(responsavel, profundidade)


# =========================
#   Operações em massa
# =========================
@transaction.atomic
def upsert_cliente_por_cpf_cnpj(data: Dict[str, Any]) -> Tuple[Cliente, bool]:
    """
    Atualiza se existir (por cpf_cnpj), senão cria. Retorna (cliente, created).
    """
    if "cpf_cnpj" not in data:
        raise ValidationError("Campo 'cpf_cnpj' é obrigatório.")

    data = {**data}
    doc = _clean_doc(data["cpf_cnpj"])
    data["cpf_cnpj"] = doc

    cliente = Cliente.objects.filter(cpf_cnpj=doc).first()
    if cliente:
        # remove cpf_cnpj de data para evitar unicidade contra si próprio
        data.pop("cpf_cnpj", None)
        return atualizar_cliente(cliente.id, data), False
    return criar_cliente(data), True


@transaction.atomic
def vincular_varios_responsaveis(
    dependente_id: int,
    responsaveis: Iterable[Tuple[int, str]]  # (responsavel_id, tipo)
) -> List[VinculoCliente]:
    """
    Vincula diversos responsáveis a um mesmo dependente.
    """
    results = []
    for responsavel_id, tipo in responsaveis:
        results.append(
            vincular_responsavel_dependente(responsavel_id, dependente_id, tipo=tipo)
        )
    return results


# --- IMPORTS adicionais ---
from io import BytesIO
from openpyxl import load_workbook, Workbook
from openpyxl.utils import get_column_letter
from django.utils.timezone import make_aware
from datetime import datetime
from django.db import IntegrityError

# ============================================================
#   IMPORTAÇÃO DE CLIENTES A PARTIR DE EXCEL
# ============================================================
def importar_clientes_de_excel(
    file_or_path,
    *,
    sheet_name: str | None = None,
    strategy: str = "upsert",
) -> dict:
    """
    Importa clientes a partir de uma planilha Excel.
    - file_or_path: caminho do arquivo, file-like (BytesIO) ou UploadedFile (Django).
    - sheet_name: se None, usa a planilha ativa.
    - strategy: "upsert" (padrão) ou "create". No "upsert", atualiza se já existir (CPF/CNPJ).

    Colunas reconhecidas (case-insensitive; acentos e pontuação ignorados):
      Identificação/contato/endereço:
        - cpf_cnpj, nome_razao, data_nascimento, telefone_emergencial, telefone_celular,
          email, cep, numero_id, logradouro, bairro, complemento, municipio, estado, ativo
      Vínculo (opcionais; se preenchidas e válidas, cria/atualiza):
        - responsavel_cpf_cnpj, tipo_vinculo, inicio_vinculo, fim_vinculo, observacoes_vinculo

    Retorna um relatório:
      {
        "total_linhas": int,
        "sucesso": int,
        "atualizados": int,
        "criados": int,
        "vinculos_criados": int,
        "erros": [ {"linha": int, "erro": "msg"} , ...]
      }
    """
    # Mapeamento canônico de headers → campos do modelo
    header_map = {
        "cpf": "cpf_cnpj",
        "cpf_cnpj": "cpf_cnpj",
        "cnpj": "cpf_cnpj",
        "nome": "nome_razao",
        "nome_razao": "nome_razao",
        "razao social": "nome_razao",
        "data_nascimento": "data_nascimento",
        "data de nascimento": "data_nascimento",
        "telefone_emergencial": "telefone_emergencial",
        "telefone emergencial": "telefone_emergencial",
        "telefone_celular": "telefone_celular",
        "telefone celular": "telefone_celular",
        "email": "email",
        "e-mail": "email",
        "cep": "cep",
        "numero": "numero_id",
        "número/id": "numero_id",
        "numero/id": "numero_id",
        "numero_id": "numero_id",
        "logradouro": "logradouro",
        "bairro": "bairro",
        "complemento": "complemento",
        "municipio": "municipio",
        "município": "municipio",
        "estado": "estado",
        "uf": "estado",
        "ativo": "ativo",
        # vínculo
        "responsavel": "responsavel_cpf_cnpj",
        "responsavel_cpf_cnpj": "responsavel_cpf_cnpj",
        "responsável": "responsavel_cpf_cnpj",
        "tipo_vinculo": "tipo_vinculo",
        "tipo vínculo": "tipo_vinculo",
        "inicio_vinculo": "inicio_vinculo",
        "início_vínculo": "inicio_vinculo",
        "fim_vinculo": "fim_vinculo",
        "observacoes_vinculo": "observacoes_vinculo",
        "observações_vínculo": "observacoes_vinculo",
    }

    def norm(s: str) -> str:
        import unicodedata, re
        s = str(s or "").strip().lower()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^a-z0-9_/ ]+", " ", s)
        s = re.sub(r"\s+", " ", s)
        return s

    def parse_bool(v):
        if v is None: return None
        s = str(v).strip().lower()
        return s in ("1", "true", "t", "sim", "s", "yes", "y")

    def parse_date(v):
        if not v: return None
        if isinstance(v, datetime): return v.date()
        if isinstance(v, (int, float)):  # datas em número Excel
            # openpyxl já converte normalmente; se chegar aqui, tentamos por string
            v = str(v)
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(str(v), fmt).date()
            except ValueError:
                continue
        return None

    # Abre workbook
    wb = load_workbook(file_or_path, data_only=True)
    ws = wb[sheet_name] if sheet_name in wb.sheetnames else (wb.active if sheet_name is None else wb.active)

    # Lê header
    headers = [norm(c.value) for c in next(ws.iter_rows(min_row=1, max_row=1))]
    col_to_field = {}
    for idx, h in enumerate(headers):
        if h in header_map:
            col_to_field[idx] = header_map[h]

    # Verificações mínimas
    required = {"cpf_cnpj", "nome_razao"}
    if not required.issubset(set(col_to_field.values())):
        faltando = required - set(col_to_field.values())
        raise ValidationError(f"Planilha incompleta. Faltam colunas: {', '.join(sorted(faltando))}")

    rel = {
        "total_linhas": 0,
        "sucesso": 0,
        "atualizados": 0,
        "criados": 0,
        "vinculos_criados": 0,
        "erros": [],
    }

    # Percorre linhas
    for i, row in enumerate(ws.iter_rows(min_row=2), start=2):
        rel["total_linhas"] += 1
        try:
            data = {}
            vinc = {}

            for idx, cell in enumerate(row):
                field = col_to_field.get(idx)
                if not field:
                    continue
                val = cell.value

                if field == "cpf_cnpj":
                    val = _clean_doc(val)
                elif field == "data_nascimento":
                    val = parse_date(val)
                elif field == "ativo":
                    val = parse_bool(val)
                elif field in ("inicio_vinculo", "fim_vinculo"):
                    vinc[field] = parse_date(val)
                    continue
                elif field in ("responsavel_cpf_cnpj", "tipo_vinculo", "observacoes_vinculo"):
                    vinc[field] = val
                    continue

                data[field] = val

            if not data.get("cpf_cnpj"):
                raise ValidationError("CPF/CNPJ vazio.")

            # Cria/Atualiza
            if strategy == "create":
                cliente = criar_cliente(data)
                rel["criados"] += 1
            else:
                cliente, created = upsert_cliente_por_cpf_cnpj(data)
                if created:
                    rel["criados"] += 1
                else:
                    rel["atualizados"] += 1

            # Vínculo opcional
            if vinc.get("responsavel_cpf_cnpj"):
                resp_doc = _clean_doc(vinc["responsavel_cpf_cnpj"])
                try:
                    responsavel = obter_cliente_por_cpf_cnpj(resp_doc)
                except ClienteNaoEncontrado:
                    # se o responsável não existe, criamos um placeholder mínimo (pode-se mudar a política)
                    responsavel = criar_cliente({
                        "cpf_cnpj": resp_doc,
                        "nome_razao": f"RESP-{resp_doc}",
                        "ativo": True,
                    })
                tipo = (vinc.get("tipo_vinculo") or "OUTRO").upper()
                _ = vincular_responsavel_dependente(
                    responsavel_id=responsavel.id,
                    dependente_id=cliente.id,
                    tipo=tipo,
                    inicio=vinc.get("inicio_vinculo"),
                    fim=vinc.get("fim_vinculo"),
                    observacoes=vinc.get("observacoes_vinculo") or "",
                )
                rel["vinculos_criados"] += 1

            rel["sucesso"] += 1

        except Exception as e:
            rel["erros"].append({"linha": i, "erro": str(e)})

    return rel


# ============================================================
#   EXPORTAÇÃO DE CLIENTES PARA EXCEL (Clientes + Vínculos)
# ============================================================
def exportar_clientes_para_excel(queryset=None) -> tuple[str, bytes]:
    """
    Exporta clientes e vínculos para um arquivo Excel (em memória).
    - queryset: se None, exporta todos os clientes ativos.

    Retorna: (filename, binary_bytes)
    Planilhas:
      - "Clientes": dados cadastrais
      - "Vinculos": colunas (responsavel_cpf_cnpj, responsavel_nome, dependente_cpf_cnpj, dependente_nome, tipo, inicio, fim, observacoes)
    """
    qs = queryset if queryset is not None else Cliente.objects.all().order_by("nome_razao")

    wb = Workbook()
    ws_cli = wb.active
    ws_cli.title = "Clientes"

    # Cabeçalhos Clientes (ordem estável)
    headers_cli = [
        "cpf_cnpj",
        "nome_razao",
        "data_nascimento",
        "telefone_emergencial",
        "telefone_celular",
        "email",
        "cep",
        "numero_id",
        "logradouro",
        "bairro",
        "complemento",
        "municipio",
        "estado",
        "ativo",
        "date_joined",     # se quiser adicionar metadados no futuro
        "id",              # PK do cliente
    ]
    ws_cli.append(headers_cli)

    for c in qs:
        ws_cli.append([
            c.cpf_cnpj,
            c.nome_razao,
            c.data_nascimento.isoformat() if c.data_nascimento else "",
            c.telefone_emergencial or "",
            c.telefone_celular or "",
            c.email or "",
            c.cep or "",
            c.numero_id or "",
            c.logradouro or "",
            c.bairro or "",
            c.complemento or "",
            c.municipio or "",
            c.estado or "",
            bool(c.ativo),
            "",  # date_joined não existe no modelo Cliente; reservado para futuro
            c.id,
        ])

    # Auto largura simples
    for col in range(1, ws_cli.max_column + 1):
        ws_cli.column_dimensions[get_column_letter(col)].width = 18

    # Aba de Vínculos
    ws_v = wb.create_sheet("Vinculos")
    headers_v = [
        "responsavel_cpf_cnpj",
        "responsavel_nome",
        "dependente_cpf_cnpj",
        "dependente_nome",
        "tipo",
        "inicio",
        "fim",
        "observacoes",
        "vinculo_id",
    ]
    ws_v.append(headers_v)

    for v in VinculoCliente.objects.select_related("responsavel", "dependente").all().order_by("responsavel__nome_razao", "dependente__nome_razao"):
        ws_v.append([
            v.responsavel.cpf_cnpj,
            v.responsavel.nome_razao,
            v.dependente.cpf_cnpj,
            v.dependente.nome_razao,
            v.tipo,
            v.inicio.isoformat() if v.inicio else "",
            v.fim.isoformat() if v.fim else "",
            v.observacoes or "",
            v.id,
        ])

    for col in range(1, ws_v.max_column + 1):
        ws_v.column_dimensions[get_column_letter(col)].width = 22

    # Salva em memória
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    filename = f"clientes_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return filename, bio.read()
