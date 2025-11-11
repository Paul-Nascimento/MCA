from django.db import models
from django.core.validators import RegexValidator, EmailValidator
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Group


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

    # ✅ Novos campos
    rg = models.CharField("RG", max_length=20, blank=True)
    registro_cref = models.CharField("Registro CREF", max_length=30, blank=True)
    tam_uniforme = models.CharField("Tamanho do Uniforme", max_length=10, blank=True)
    data_nascimento = models.DateField("Data de Nascimento", null=True, blank=True)
    data_admissao = models.DateField("Data de Admissão", null=True, blank=True)

    class Cargo(models.TextChoices):
        ADMINISTRATIVO = "ADMIN", "Administrativo"
        FINANCEIRO = "FIN", "Financeiro"
        RH = "RH", "Recursos Humanos"
        PROFESSOR = "PROF", "Professor"    # ✅ alterado
        DIRETOR = "DIR", "Diretoria"
        OUTRO = "OUTRO", "Outro"

    cargo = models.CharField(
        "Cargo",
        max_length=20,
        choices=Cargo.choices,
        default=Cargo.OUTRO,
        db_index=True
    )

    class RegimeTrabalhista(models.TextChoices):
        CLT_HORISTA = "CLT_HORISTA", "CLT Horista"   # ✅ alterado
        CLT_NORMAL = "CLT_NORMAL", "CLT Normal"     # ✅ alterado
        ESTAGIARIO = "ESTAGIARIO", "Estagiário"
        PJ = "PJ", "Pessoa Jurídica"
        OUTRO = "OUTRO", "Outro"

    regime_trabalhista = models.CharField(
        "Regime Trabalhista",
        max_length=20,
        choices=RegimeTrabalhista.choices,
        default=RegimeTrabalhista.OUTRO,
        db_index=True,
    )

    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["nome", "id"]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["ativo"]),
            models.Index(fields=["cargo"]),
        ]
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"

    def __str__(self):
        return f"{self.nome} ({self.cpf_cnpj}) - {self.get_cargo_display()}"
    

        # ✅ Retorna o papel de acesso (para facilitar uso nas views/templates)
    def is_admin(self):
        return self.cargo in [self.Cargo.ADMINISTRATIVO, self.Cargo.DIRETOR]

    def is_professor(self):
        return self.cargo == self.Cargo.PROFESSOR

    def is_financeiro(self):
        return self.cargo == self.Cargo.FINANCEIRO

    def is_rh(self):
        return self.cargo == self.Cargo.RH
    

    # ✅ Regra: se cargo for professor, CREF é obrigatório
    def clean(self):
        if self.cargo == Funcionario.Cargo.PROFESSOR and not self.registro_cref:
            raise ValidationError({"registro_cref": "Registro CREF é obrigatório para professores."})


from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

@receiver(post_save, sender=Funcionario)
def criar_usuario_para_funcionario(sender, instance, created, **kwargs):
    """
    Cria automaticamente um User vinculado ao Funcionario e adiciona-o ao grupo correto.
    """
    from django.contrib.auth.models import User, Group

    # 1️⃣ Cria o usuário, se ainda não existir
    if created and not instance.user:
        username = instance.nome.lower().replace(" ", ".")
        user = User.objects.create_user(
            username=username,
            password="mca123",  # senha temporária (pode exigir troca depois)
            first_name=instance.nome.split(" ")[0],
            last_name=" ".join(instance.nome.split(" ")[1:]),
        )
        instance.user = user
        instance.save()

    # 2️⃣ Garante que os grupos necessários existem
    for nome_grupo in ["Diretoria", "Professor", "Estagiario"]:
        Group.objects.get_or_create(name=nome_grupo)

    # 3️⃣ Define o grupo com base no cargo ou regime trabalhista
    user = instance.user
    if not user:
        return  # segurança extra

    # limpa grupos anteriores
    user.groups.clear()

    if instance.cargo == Funcionario.Cargo.DIRETOR:
        grupo = Group.objects.get(name="Diretoria")
    elif instance.cargo == Funcionario.Cargo.PROFESSOR:
        grupo = Group.objects.get(name="Professor")
    elif instance.regime_trabalhista == Funcionario.RegimeTrabalhista.ESTAGIARIO:
        grupo = Group.objects.get(name="Estagiario")
    else:
        grupo = None

    # 4️⃣ Atribui o grupo, se aplicável
    if grupo:
        user.groups.add(grupo)
        user.save()


