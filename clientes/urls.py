# clientes/urls.py
from django.urls import path
from . import views

app_name = "clientes"

# urls.py
urlpatterns = [
    path("clientes/", views.list_clientes, name="list"),
    path("clientes/criar/", views.create_cliente, name="create"),
    path("clientes/<int:pk>/atualizar/", views.update_cliente, name="update"),
    path("clientes/<int:pk>/status/", views.toggle_status, name="toggle_status"),

    # Página com termos (GET) + confirmação via POST
    path("clientes/aceite/<str:token>/", views.aceite_contrato, name="aceite"),
    # One-click (GET) para confirmar direto
    path("clientes/aceite/<str:token>/confirmar/", views.aceite_confirmar, name="aceite_confirmar"),

    path("exportar/", views.exportar, name="exportar"),
    path("<int:pk>/ativar/", views.toggle_status, name="ativar"),
]
