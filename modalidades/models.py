from django.db import models
from django.utils.text import slugify

class Modalidade(models.Model):
    nome = models.CharField("Nome", max_length=100)
    slug = models.SlugField("Slug", max_length=120, unique=True, blank=True)
    descricao = models.TextField("Descrição", blank=True)
    ativo = models.BooleanField(default=True)

    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["nome", "id"]
        verbose_name = "Modalidade"
        verbose_name_plural = "Modalidades"
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        # Gera slug único a partir do nome, se não informado
        if not self.slug and self.nome:
            base = slugify(self.nome)
            slug = base or "modalidade"
            i = 2
            cls = self.__class__
            while cls.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)
