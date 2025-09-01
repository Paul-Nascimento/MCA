from django.urls import path
from . import views

app_name = "condominios"

urlpatterns = [
    path("condominios/", views.list_condominios, name="list"),
    path("condominios/criar/", views.create_condominio, name="create"),
    path("condominios/<int:pk>/atualizar/", views.update_condominio, name="update"),
    path("condominios/exportar/", views.exportar_condominios_view, name="exportar"),
    path("condominios/importar/", views.importar_condominios_view, name="importar"),
]
