from django.urls import path
from . import views

app_name = "clientes"

urlpatterns = [
    path("clientes/", views.list_clientes, name="list"),
    path("clientes/criar/", views.create_cliente, name="create"),
    path("clientes/<int:pk>/atualizar/", views.update_cliente, name="update"),
    path("clientes/exportar/", views.exportar_clientes_view, name="exportar"),
    path("clientes/importar/", views.importar_clientes_view, name="importar"),
]
