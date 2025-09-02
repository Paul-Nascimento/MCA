from django.contrib import admin
from .models import Funcionario

@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "regime_trabalhista", "ativo")
    list_filter  = ("regime_trabalhista", "ativo")
    search_fields = ("nome", "email")