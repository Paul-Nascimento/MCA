from django.contrib import admin
from .models import Funcionario

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Funcionario

@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ("id", "nome", "regime_trabalhista", "ativo")
    list_filter  = ("regime_trabalhista", "ativo")
    search_fields = ("nome", "email")

class FuncionarioInline(admin.StackedInline):
    model = Funcionario
    can_delete = False
    verbose_name_plural = "Funcionário"
    fk_name = "user"

class UserAdmin(BaseUserAdmin):
    inlines = (FuncionarioInline, )

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []  # evita erro ao criar novo user
        return super().get_inline_instances(request, obj)

# Re-registra o User admin com inline
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


