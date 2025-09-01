from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

DIAS_SEMANA = [
    (0, "Segunda"),
    (1, "Terça"),
    (2, "Quarta"),
    (3, "Quinta"),
    (4, "Sexta"),
    (5, "Sábado"),
    (6, "Domingo"),
]

class Turma(models.Model):
    # Relações
    professor = models.ForeignKey(
        "funcionarios.Funcionario",
        on_delete=models.PROTECT,
        related_name="turmas"
    )
    modalidade = models.ForeignKey(
        "modalidades.Modalidade",
        on_delete=models.PROTECT,
        related_name="turmas"
    )
    condominio = models.ForeignKey(
        "condominios.Condominio",
        on_delete=models.PROTECT,
        related_name="turmas"
    )

    # Regras da turma
    nome_exibicao = models.CharField("Nome (opcional)", max_length=255, blank=True)
    valor = models.DecimalField("Valor", max_digits=10, decimal_places=2,
                                validators=[MinValueValidator(Decimal("0.00"))])
    capacidade = models.PositiveIntegerField("Capacidade (máx. alunos)", validators=[MinValueValidator(1)])

    # Horário (recorrente semanal)
    dia_semana = models.PositiveSmallIntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    duracao_minutos = models.PositiveIntegerField(default=60, validators=[MinValueValidator(1)])

    # Vigência
    inicio_vigencia = models.DateField()
    fim_vigencia = models.DateField(null=True, blank=True)

    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["condominio__nome", "modalidade__nome", "dia_semana", "hora_inicio", "id"]
        indexes = [
            models.Index(fields=["professor", "dia_semana", "hora_inicio"]),
            models.Index(fields=["condominio"]),
            models.Index(fields=["ativo"]),
        ]
        verbose_name = "Turma"
        verbose_name_plural = "Turmas"

    def __str__(self):
        base = self.nome_exibicao or f"{self.modalidade} - {self.condominio}"
        return f"{base} ({self.get_dia_semana_display()} {self.hora_inicio:%H:%M})"

    @property
    def hora_fim(self):
        # retornamos um time aproximado somando a duração
        from datetime import datetime, timedelta
        dt = datetime.combine(self.inicio_vigencia, self.hora_inicio) + timedelta(minutes=self.duracao_minutos)
        return dt.time()


class ListaPresenca(models.Model):
    turma = models.ForeignKey("turmas.Turma", on_delete=models.PROTECT, related_name="listas_presenca")
    data = models.DateField()
    observacao_geral = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("turma", "data")]
        ordering = ["-data", "-id"]
        indexes = [
            models.Index(fields=["turma", "data"]),
        ]
        verbose_name = "Lista de presença"
        verbose_name_plural = "Listas de presença"

    def __str__(self):
        return f"{self.turma} — {self.data:%d/%m/%Y}"

    @property
    def total_presentes(self) -> int:
        return self.itens.filter(presente=True).count()

    @property
    def total_itens(self) -> int:
        return self.itens.count()


class ItemPresenca(models.Model):
    lista = models.ForeignKey(ListaPresenca, on_delete=models.CASCADE, related_name="itens")
    # Mantemos referência ao cliente e (opcionalmente) à matrícula
    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.PROTECT, related_name="presencas")
    matricula = models.ForeignKey("turmas.Matricula", on_delete=models.PROTECT, null=True, blank=True, related_name="presencas")

    presente = models.BooleanField(default=False)
    observacao = models.CharField(max_length=255, blank=True)

    # Snapshot (para manter histórico mesmo que o cliente renomeie depois)
    cliente_nome_snapshot = models.CharField(max_length=255)
    cliente_doc_snapshot = models.CharField(max_length=20)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("lista", "cliente")]
        ordering = ["cliente_nome_snapshot", "id"]
        indexes = [
            models.Index(fields=["lista"]),
            models.Index(fields=["cliente"]),
        ]
        verbose_name = "Item de presença"
        verbose_name_plural = "Itens de presença"

    def __str__(self):
        return f"{self.cliente_nome_snapshot} — {'Presente' if self.presente else 'Ausente'}"


class Matricula(models.Model):
    turma = models.ForeignKey(Turma, on_delete=models.PROTECT, related_name="matriculas")
    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.PROTECT, related_name="matriculas")

    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    ativa = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ativa", "turma", "cliente__nome_razao"]
        unique_together = []  # validamos via service para permitir histórico
        indexes = [
            models.Index(fields=["turma", "ativa"]),
            models.Index(fields=["cliente", "ativa"]),
        ]
        verbose_name = "Matrícula"
        verbose_name_plural = "Matrículas"

    def __str__(self):
        status = "ativa" if self.ativa else "inativa"
        return f"{self.cliente} em {self.turma} ({status})"
