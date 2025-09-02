# clientes/models.py
from django.db import models

UF_CHOICES = [
    ("AC","AC"),("AL","AL"),("AM","AM"),("AP","AP"),("BA","BA"),("CE","CE"),("DF","DF"),
    ("ES","ES"),("GO","GO"),("MA","MA"),("MG","MG"),("MS","MS"),("MT","MT"),("PA","PA"),
    ("PB","PB"),("PE","PE"),("PI","PI"),("PR","PR"),("RJ","RJ"),("RN","RN"),("RO","RO"),
    ("RR","RR"),("RS","RS"),("SC","SC"),("SE","SE"),("SP","SP"),("TO","TO"),
]

class Cliente(models.Model):
    cpf_cnpj = models.CharField(max_length=18, unique=True)  # armazene formatado ou só dígitos; normalize nos services
    nome_razao = models.CharField(max_length=255)
    data_nascimento = models.DateField(null=True, blank=True)
    telefone_emergencial = models.CharField(max_length=20, blank=True)
    telefone_celular = models.CharField(max_length=20, blank=True)

    cep = models.CharField(max_length=10, blank=True)
    numero_id = models.CharField(max_length=20, blank=True)
    logradouro = models.CharField(max_length=255, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    complemento = models.CharField(max_length=100, blank=True,null=True)
    municipio = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, choices=UF_CHOICES, blank=True)

    email = models.EmailField(blank=True)

    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    contrato_aceito = models.BooleanField(default=False)
    contrato_aceito_em = models.DateTimeField(null=True, blank=True)
    contrato_token = models.CharField(max_length=64, blank=True, db_index=True)
    contrato_token_expira_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nome_razao", "id"]
        indexes = [
            models.Index(fields=["nome_razao"]),
            models.Index(fields=["cpf_cnpj"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.nome_razao} — {self.cpf_cnpj}"
