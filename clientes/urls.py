# clientes/urls.py
from django.urls import path
from . import views

app_name = "clientes"

urlpatterns = [
    path("clientes/", views.list_clientes, name="list"),
    path("clientes/criar/", views.create_cliente, name="create"),
    path("clientes/<int:pk>/atualizar/", views.update_cliente, name="update"),
    path("clientes/<int:pk>/ativar/", views.ativar_cliente, name="ativar"),
    path("clientes/importar/", views.importar_excel_view, name="importar"),
    path("clientes/exportar/", views.exportar_excel_view, name="exportar"),
]
