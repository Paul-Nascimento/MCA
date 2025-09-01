from django.db import models
from django.core.validators import RegexValidator, EmailValidator

# UF (mesmo padrão usado em Clientes)
UF_CHOICES = [
    ('AC','AC'),('AL','AL'),('AM','AM'),('AP','AP'),('BA','BA'),('CE','CE'),
    ('DF','DF'),('ES','ES'),('GO','GO'),('MA','MA'),('MG','MG'),('MS','MS'),
    ('MT','MT'),('PA','PA'),('PB','PB'),('PE','PE'),('PI','PI'),('PR','PR'),
    ('RJ','RJ'),('RN','RN'),('RO','RO'),('RR','RR'),('RS','RS'),('SC','SC'),
    ('SE','SE'),('SP','SP'),('TO','TO'),
]

CNPJ_VALIDATOR = RegexValidator(
    regex=r'^\d{14}$',
    message="CNPJ deve conter exatamente 14 dígitos (somente números)."
)

class Condominio(models.Model):
    # Cadastro
    cnpj = models.CharField("CNPJ", max_length=14, unique=True, validators=[CNPJ_VALIDATOR])
    nome = models.CharField("Nome Completo", max_length=255)
    email = models.EmailField("E-mail", blank=True, validators=[EmailValidator()])

    # Endereço
    cep = models.CharField("CEP", max_length=9, blank=True)
    numero = models.CharField("Número", max_length=20, blank=True)
    logradouro = models.CharField("Logradouro", max_length=255, blank=True)
    bairro = models.CharField("Bairro", max_length=255, blank=True)
    complemento = models.CharField("Complemento", max_length=255, blank=True)
    municipio = models.CharField("Município", max_length=255, blank=True)
    estado = models.CharField("Estado (UF)", max_length=2, choices=UF_CHOICES, blank=True)

    # Controle
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["municipio", "estado"]),
            models.Index(fields=["ativo"]),
        ]
        verbose_name = "Condomínio"
        verbose_name_plural = "Condomínios"

    def __str__(self):
        local = f"{self.municipio}/{self.estado}" if self.municipio or self.estado else "-"
        return f"{self.nome} ({local})"
