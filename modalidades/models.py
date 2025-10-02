from django.db import models
from django.utils.text import slugify

# modalidades/models.py
from django.db import models
from django.utils.text import slugify
# ADICIONE:
from condominios.models import Condominio

class Modalidade(models.Model):
    nome = models.CharField("Nome", max_length=100)
    slug = models.SlugField("Slug", max_length=120, unique=True, blank=True)
    descricao = models.TextField("Descrição", blank=True)
    ativo = models.BooleanField(default=True)

    # NOVO: Modalidade pertence a um Condomínio
    condominio = models.ForeignKey(
        Condominio,
        on_delete=models.CASCADE,
        related_name="modalidades",
        verbose_name="Condomínio",
        # 1ª migração: deixe null=True temporariamente, preencha os existentes,
        # 2ª migração: torne null=False (ver seção de Migração).
        null=True, blank=True
    )

    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["nome", "id"]
        verbose_name = "Modalidade"
        verbose_name_plural = "Modalidades"
        # NOVO: não permitir "Futebol" duplicado no mesmo condomínio
        constraints = [
            models.UniqueConstraint(
                fields=["condominio", "nome"],
                name="uniq_modalidade_por_condominio_nome",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome or "")
        super().save(*args, **kwargs)

    def __str__(self):
        # ajuda na identificação visual
        return f"{self.nome} — {self.condominio.nome if self.condominio_id else 'SEM CONDOMÍNIO'}"

