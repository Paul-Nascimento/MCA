# modalidades/admin.py
from django.contrib import admin
from .models import Modalidade

@admin.register(Modalidade)
class ModalidadeAdmin(admin.ModelAdmin):
    list_display = ("nome","condominio","ativo")
    list_filter = ("condominio","ativo")
    search_fields = ("nome","condominio__nome")
    ordering = ("condominio__nome","nome")
