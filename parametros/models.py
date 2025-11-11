# parametros/models.py
from django.db import models

class ParametroContrato(models.Model):
    nome = models.CharField("Nome do Modelo", max_length=100, unique=True)
    assunto_email = models.CharField("Assunto do e-mail", max_length=200)
    corpo_email = models.TextField(
        "Corpo do e-mail",
        help_text="Você pode usar variáveis como {{ cliente.nome_razao }} e {{ cliente.cpf_cnpj }}."
    )
    corpo_contrato = models.TextField(
        "Template do contrato (HTML)",
        help_text="Use HTML básico e variáveis Jinja como {{ cliente.nome_razao }}."
    )
    ativo = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nome} ({'Ativo' if self.ativo else 'Inativo'})"
