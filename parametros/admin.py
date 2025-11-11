# parametros/admin.py
from django.contrib import admin
from .models import ParametroContrato

@admin.register(ParametroContrato)
class ParametroContratoAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "updated_at")
    list_editable = ("ativo",)
    search_fields = ("nome", "corpo_email", "corpo_contrato")
    ordering = ("nome",)
    fieldsets = (
        (None, {
            "fields": ("nome", "assunto_email", "corpo_email", "corpo_contrato", "ativo")
        }),
    )
