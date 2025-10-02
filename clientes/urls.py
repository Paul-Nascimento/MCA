# clientes/urls.py
from django.urls import path
from . import views

app_name = "clientes"

urlpatterns = [
    path("clientes/", views.list_clientes, name="list"),
    path("clientes/criar/", views.create_cliente, name="create"),
    path("clientes/<int:pk>/atualizar/", views.update_cliente, name="update"),
    # NOVO: alternar status entre Ativo/Inativo
    path("clientes/<int:pk>/status/", views.toggle_status, name="toggle_status"),
    # (já existentes)
    path("clientes/aceite/<str:token>/", views.aceite_contrato, name="aceite"),
    # path("clientes/<int:pk>/reenviar-convite/", views.reenviar_convite, name="reenviar_convite"),  # opcional
    path("exportar/", views.exportar, name="exportar"),
    path("<int:pk>/ativar/", views.toggle_status, name="ativar"),  # 👈 ADICIONE ESTA LINHA
]