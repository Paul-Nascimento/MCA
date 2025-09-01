from django.urls import path
from . import views

app_name = "funcionarios"

urlpatterns = [
    path("funcionarios/", views.list_funcionarios, name="list"),
    path("funcionarios/criar/", views.create_funcionario, name="create"),
    path("funcionarios/<int:pk>/atualizar/", views.update_funcionario, name="update"),
    path("funcionarios/exportar/", views.exportar_funcionarios_view, name="exportar"),
    path("funcionarios/importar/", views.importar_funcionarios_view, name="importar"),
]
