from django.contrib import admin
from .models import Modalidade

@admin.register(Modalidade)
class ModalidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "slug", "updated_at")
    list_filter  = ("ativo",)
    search_fields = ("nome", "slug", "descricao")
    ordering = ("nome",)
