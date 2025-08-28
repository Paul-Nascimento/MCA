# apps/clientes/models.py
from django.db import models
from django.core.validators import RegexValidator, EmailValidator

CPF_CNPJ_VALIDATOR = RegexValidator(
    regex=r'^\d{11}(\d{3})?$|^\d{14}$',  # 11 (CPF) ou 14 (CNPJ) dígitos
    message="Informe apenas dígitos: 11 para CPF ou 14 para CNPJ."
)

UF_CHOICES = [
    ('AC','AC'),('AL','AL'),('AM','AM'),('AP','AP'),('BA','BA'),('CE','CE'),
    ('DF','DF'),('ES','ES'),('GO','GO'),('MA','MA'),('MG','MG'),('MS','MS'),
    ('MT','MT'),('PA','PA'),('PB','PB'),('PE','PE'),('PI','PI'),('PR','PR'),
    ('RJ','RJ'),('RN','RN'),('RO','RO'),('RR','RR'),('RS','RS'),('SC','SC'),
    ('SE','SE'),('SP','SP'),('TO','TO'),
]

class Cliente(models.Model):
    # Identificação
    cpf_cnpj = models.CharField(
        "CPF/CNPJ", max_length=14, unique=True, validators=[CPF_CNPJ_VALIDATOR]
    )
    nome_razao = models.CharField("Nome Completo / Razão Social", max_length=255)
    data_nascimento = models.DateField("Data de Nascimento", null=True, blank=True)

    # Contato
    telefone_emergencial = models.CharField("Telefone Emergencial", max_length=20, blank=True)
    telefone_celular = models.CharField("Telefone Celular", max_length=20, blank=True)
    email = models.EmailField("E-mail", blank=True, validators=[EmailValidator()])

    # Endereço
    cep = models.CharField("CEP", max_length=9, blank=True)  # pode armazenar com máscara
    numero_id = models.CharField("Número/ID", max_length=20, blank=True)
    logradouro = models.CharField("Logradouro", max_length=255, blank=True)
    bairro = models.CharField("Bairro", max_length=255, blank=True)
    complemento = models.CharField("Complemento", max_length=255, blank=True)
    municipio = models.CharField("Município", max_length=255, blank=True)
    estado = models.CharField("Estado", max_length=2, choices=UF_CHOICES, blank=True)

    # Relacionamentos (responsáveis ↔ dependentes)
    relacoes = models.ManyToManyField(
        'self',
        through='VinculoCliente',
        symmetrical=False,
        related_name='relacionados'
    )

    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nome_razao']

    def __str__(self):
        return f"{self.nome_razao} ({self.cpf_cnpj})"

    # Helpers de conveniência
    @property
    def responsaveis(self):
        return (Cliente.objects
                .filter(vinculos_saida__dependente=self, vinculos_saida__papel='RESPONSAVEL')
                .distinct())

    @property
    def dependentes(self):
        return (Cliente.objects
                .filter(vinculos_entrada__responsavel=self, vinculos_entrada__papel='RESPONSAVEL')
                .distinct())


class VinculoCliente(models.Model):
    PAPEL_CHOICES = [
        ('RESPONSAVEL', 'Responsável'),
        ('DEPENDENTE', 'Dependente'),  # direção inversa, ver validação abaixo
    ]
    TIPO_VINCULO = [
        ('PAI', 'Pai'),
        ('MAE', 'Mãe'),
        ('TUTOR', 'Tutor(a)'),
        ('CONJUGE', 'Cônjuge'),
        ('OUTRO', 'Outro'),
    ]

    # Direção do vínculo (não simétrico):
    responsavel = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name='vinculos_entrada'
    )
    dependente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name='vinculos_saida'
    )

    # Metadados do vínculo
    papel = models.CharField(max_length=12, choices=PAPEL_CHOICES, default='RESPONSAVEL')
    tipo = models.CharField(max_length=10, choices=TIPO_VINCULO, default='OUTRO')
    inicio = models.DateField(null=True, blank=True)
    fim = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        unique_together = [('responsavel', 'dependente', 'tipo')]
        verbose_name = "Vínculo de Cliente"
        verbose_name_plural = "Vínculos de Clientes"

    def clean(self):
        # Evita auto-vínculo e ciclos simples:
        if self.responsavel_id == self.dependente_id:
            from django.core.exceptions import ValidationError
            raise ValidationError("Um cliente não pode ser responsável de si mesmo.")

        # Normaliza o campo 'papel' para manter coerência:
        # Para este design, sempre considere que este registro representa
        # 'responsavel' -> 'dependente'. Mantemos papel='RESPONSAVEL'.
        self.papel = 'RESPONSAVEL'

    def __str__(self):
        return f"{self.responsavel} → {self.dependente} ({self.tipo})"
