# funcionarios/admin.py
from django.contrib import admin
from .models import Funcionario

@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ("nome", "cpf_cnpj", "email", "telefone", "ativo")
    search_fields = ("nome", "cpf_cnpj", "email")
    list_filter = ("ativo",)
    ordering = ("nome",)
