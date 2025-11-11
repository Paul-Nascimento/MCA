from django.urls import path
from . import views

app_name = "parametros"

urlpatterns = [
    path("", views.listar_contratos, name="listar_contratos"),
    path("<int:pk>/editar/", views.editar_contrato, name="editar_contrato"),
    path("novo/", views.criar_contrato, name="criar_contrato"),  # 👈 nova rota
]
