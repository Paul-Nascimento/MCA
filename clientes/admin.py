# clientes/admin.py
from django.contrib import admin
from .models import Cliente

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nome_razao", "cpf_cnpj", "email", "condominio", "ativo")
    list_filter = ("ativo", "condominio", "estado")
    search_fields = ("nome_razao", "cpf_cnpj", "email")
    ordering = ("nome_razao",)