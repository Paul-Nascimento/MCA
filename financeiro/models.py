from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

TIPO_CHOICES = (
    ("RECEBER", "A Receber"),
    ("PAGAR", "A Pagar"),
)

STATUS_CHOICES = (
    ("ABERTO", "Aberto"),
    ("PARCIAL", "Parcial"),
    ("LIQUIDADO", "Liquidado"),
    ("CANCELADO", "Cancelado"),
)

FORMA_PGTO = (
    ("DINHEIRO", "Dinheiro"),
    ("PIX", "PIX"),
    ("CARTAO", "Cartão"),
    ("BOLETO", "Boleto"),
    ("TRANSF", "Transferência"),
    ("OUTRO", "Outro"),
)

class CategoriaFinanceira(models.Model):
    nome = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Categoria financeira"
        verbose_name_plural = "Categorias financeiras"

    def __str__(self):
        return self.nome


class Lancamento(models.Model):
    tipo = models.CharField(max_length=8, choices=TIPO_CHOICES)
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    data_emissao = models.DateField(auto_now_add=True)
    vencimento = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ABERTO")

    # Relacionamentos opcionais (ligue ao que fizer sentido)
    cliente = models.ForeignKey("clientes.Cliente", null=True, blank=True, on_delete=models.SET_NULL, related_name="lancamentos")
    funcionario = models.ForeignKey("funcionarios.Funcionario", null=True, blank=True, on_delete=models.SET_NULL, related_name="lancamentos")
    condominio = models.ForeignKey("condominios.Condominio", null=True, blank=True, on_delete=models.SET_NULL, related_name="lancamentos")
    turma = models.ForeignKey("turmas.Turma", null=True, blank=True, on_delete=models.SET_NULL, related_name="lancamentos")

    categoria = models.ForeignKey(CategoriaFinanceira, null=True, blank=True, on_delete=models.SET_NULL, related_name="lancamentos")

    # Caso não haja entidade cadastrada, guarde o texto:
    contraparte_nome = models.CharField(max_length=255, blank=True)
    contraparte_doc = models.CharField(max_length=20, blank=True)

    observacao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-vencimento", "-id"]
        indexes = [
            models.Index(fields=["tipo", "status"]),
            models.Index(fields=["vencimento"]),
            models.Index(fields=["cliente"]),
            models.Index(fields=["condominio"]),
            models.Index(fields=["funcionario"]),
            models.Index(fields=["turma"]),
        ]
        verbose_name = "Lançamento financeiro"
        verbose_name_plural = "Lançamentos financeiros"


    def __str__(self):
        return f"{self.get_tipo_display()} · {self.descricao} · R$ {self.valor} · {self.vencimento:%d/%m/%Y}"

    @property
    def total_baixado(self) -> Decimal:
        from django.db.models import Sum
        s = self.baixas.aggregate(s=Sum("valor"))["s"] or Decimal("0.00")
        return s

    @property
    def saldo(self) -> Decimal:
        return (self.valor or Decimal("0.00")) - self.total_baixado

    @property
    def vencido(self) -> bool:
        import datetime as _dt
        return self.status in ("ABERTO", "PARCIAL") and self.vencimento < _dt.date.today()


class Baixa(models.Model):
    lancamento = models.ForeignKey(Lancamento, on_delete=models.CASCADE, related_name="baixas")
    data = models.DateField()
    valor = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    forma = models.CharField(max_length=10, choices=FORMA_PGTO, default="PIX")
    observacao = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data", "-id"]
        indexes = [models.Index(fields=["lancamento", "data"])]

    def __str__(self):
        return f"Baixa {self.data:%d/%m/%Y} R$ {self.valor} ({self.get_forma_display()})"
