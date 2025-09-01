# condominios/admin.py
from django.contrib import admin
from .models import Condominio

@admin.register(Condominio)
class CondominioAdmin(admin.ModelAdmin):
    list_display = ("nome", "municipio", "estado", "cnpj", "ativo")
    list_filter = ("estado", "ativo")
    search_fields = ("nome", "cnpj", "municipio", "email")
    ordering = ("nome",)
