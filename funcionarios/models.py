from django.db import models
from django.core.validators import RegexValidator, EmailValidator
from django.contrib.auth.models import User

DOC_VALIDATOR = RegexValidator(
    regex=r'^(\d{11}|\d{14})$',
    message="Informe CPF (11 dígitos) ou CNPJ (14 dígitos), apenas números."
)

class Funcionario(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="funcionario",
        null=True, blank=True
    )

    cpf_cnpj = models.CharField("CPF/CNPJ", max_length=14, unique=True, validators=[DOC_VALIDATOR])
    nome = models.CharField("Nome", max_length=255)
    email = models.EmailField("E-mail", blank=True, validators=[EmailValidator()])
    telefone = models.CharField("Telefone", max_length=30, blank=True)

    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["nome", "id"]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["ativo"]),
        ]
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"

    def __str__(self):
        return f"{self.nome} ({self.cpf_cnpj})"
