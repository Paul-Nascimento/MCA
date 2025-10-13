from __future__ import annotations
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

# Conveniência para exibir nome dos dias quando necessário (útil em formulários/filtros)
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
        related_name="turmas",
    )

    modalidade = models.ForeignKey(
        "modalidades.Modalidade",
        on_delete=models.CASCADE,
        related_name="turmas",
    )

    # Regras da turma
    nome_exibicao = models.CharField("Nome (opcional)", max_length=255, blank=True)
    valor = models.DecimalField(
        "Valor",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    capacidade = models.PositiveIntegerField(
        "Capacidade (máx. alunos)", validators=[MinValueValidator(1)]
    )

    hora_inicio = models.TimeField(default="18:00")
    duracao_minutos = models.PositiveIntegerField(default=60)

    # Flags de dia (novo modelo)
    seg = models.BooleanField("Seg", default=False)
    ter = models.BooleanField("Ter", default=False)
    qua = models.BooleanField("Qua", default=False)
    qui = models.BooleanField("Qui", default=False)
    sex = models.BooleanField("Sex", default=False)
    sab = models.BooleanField("Sáb", default=False)
    dom = models.BooleanField("Dom", default=False)

    # Vigência
    inicio_vigencia = models.DateField()
    fim_vigencia = models.DateField(null=True, blank=True)

    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["modalidade__condominio__nome", "modalidade__nome", "hora_inicio", "id"]
        indexes = [
            models.Index(fields=["professor", "hora_inicio"]),
            # REMOVIDO: models.Index(fields=["condominio"]),
            models.Index(fields=["ativo"]),
        ]
        verbose_name = "Turma"
        verbose_name_plural = "Turmas"

    def clean(self):
        super().clean()
        # REMOVIDO: checagem de modalidade x condominio da própria turma
        if not any([self.seg, self.ter, self.qua, self.qui, self.sex, self.sab, self.dom]):
            raise ValidationError("Selecione ao menos um dia da semana.")
        if self.fim_vigencia and self.fim_vigencia < self.inicio_vigencia:
            raise ValidationError("A data de fim da vigência não pode ser anterior ao início.")

    @property
    def condominio(self):
        """Compat: permite usar turma.condominio como antes."""
        return self.modalidade.condominio

    

    def dias_ativos(self) -> List[int]:
        """Retorna os índices weekday() ativos: Seg=0 ... Dom=6."""
        m = {"seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6}
        return [
            m[k]
            for k, v in {
                "seg": self.seg,
                "ter": self.ter,
                "qua": self.qua,
                "qui": self.qui,
                "sex": self.sex,
                "sab": self.sab,
                "dom": self.dom,
            }.items()
            if v
        ]

    @property
    def hora_fim(self):
        """Retorna um time aproximado somando a duração à hora de início."""
        dt = datetime.combine(self.inicio_vigencia, self.hora_inicio) + timedelta(
            minutes=self.duracao_minutos
        )
        return dt.time()

    @property
    def ocupacao(self) -> int:
        """Total de matrículas ATIVAS (capacidade ocupada atual)."""
        return self.matriculas.filter(ativa=True).count()

    @property
    def lotada(self) -> bool:
        return self.ocupacao >= self.capacidade

    def __str__(self):
        nomes = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        dias = ", ".join(nomes[i] for i in self.dias_ativos()) or "—"
        base = self.nome_exibicao or f"{self.modalidade} - {self.modalidade.condominio}"
        return f"{base} ({dias} {self.hora_inicio:%H:%M})"


class ListaPresenca(models.Model):
    turma = models.ForeignKey(
        "turmas.Turma", on_delete=models.PROTECT, related_name="listas_presenca"
    )
    data = models.DateField()
    observacao_geral = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("turma", "data")]
        ordering = ["-data", "-id"]
        indexes = [models.Index(fields=["turma", "data"])]
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
    lista = models.ForeignKey(
        ListaPresenca, on_delete=models.CASCADE, related_name="itens"
    )
    # referencia opcional à matrícula (AGORA ÚNICA por lista)
    matricula = models.ForeignKey(
        "turmas.Matricula",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="presencas",
    )
    # (mantido) cliente, para relatórios/consultas
    cliente = models.ForeignKey(
        "clientes.Cliente", on_delete=models.PROTECT, related_name="presencas"
    )

    presente = models.BooleanField(default=False)
    observacao = models.CharField(max_length=255, blank=True)

    # Snapshots (usar participante se houver)
    cliente_nome_snapshot = models.CharField(max_length=255)
    cliente_doc_snapshot = models.CharField(max_length=20)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # 👇 chave de unicidade passa a ser a MATRÍCULA
        unique_together = [("lista", "matricula")]
        ordering = ["cliente_nome_snapshot", "id"]
        indexes = [
            models.Index(fields=["lista"]),
            models.Index(fields=["cliente"]),
            models.Index(fields=["matricula"]),
        ]
        verbose_name = "Item de presença"
        verbose_name_plural = "Itens de presença"

    def __str__(self):
        return f"{self.cliente_nome_snapshot} — {'Presente' if self.presente else 'Ausente'}"


SEXO_CHOICES = (("M", "Masculino"), ("F", "Feminino"), ("O", "Outro"))


class Matricula(models.Model):
    turma = models.ForeignKey(
        "turmas.Turma", on_delete=models.PROTECT, related_name="matriculas"
    )
    cliente = models.ForeignKey(
        "clientes.Cliente", on_delete=models.PROTECT, related_name="matriculas"
    )
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    ativa = models.BooleanField(default=True)

    # Participante (se vazio => o aluno é o próprio cliente)
    participante_nome = models.CharField(max_length=255, blank=True)
    participante_cpf = models.CharField(max_length=14, blank=True)  # armazene limpo
    participante_sexo = models.CharField(
        max_length=1, choices=SEXO_CHOICES, blank=True
    )
    # 👇 NOVO: idade do participante (opcional)
    participante_idade = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ativa", "cliente__nome_razao", "id"]
        indexes = [
            models.Index(fields=["turma", "ativa"]),
            models.Index(fields=["cliente"]),
        ]

    def __str__(self):
        who = self.participante_nome or self.cliente.nome_razao
        return f"{who} @ {self.turma}"
