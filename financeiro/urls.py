from django.urls import path
from . import views

app_name = "financeiro"

urlpatterns = [
    path("financeiro/", views.list_financeiro, name="list"),
    path("financeiro/criar/", views.create_lancamento, name="create"),
    path("financeiro/<int:pk>/atualizar/", views.update_lancamento, name="update"),
    path("financeiro/<int:pk>/cancelar/", views.cancelar_lancamento_view, name="cancelar"),
    path("financeiro/baixa/", views.registrar_baixa_view, name="baixa"),
    path("financeiro/baixa/<int:baixa_id>/estornar/", views.estornar_baixa_view, name="estornar"),
    path("financeiro/recorrencia/", views.gerar_recorrencia_view, name="recorrencia"),
    path("financeiro/exportar/", views.exportar_financeiro_view, name="exportar"),
     path("financeiro/mensalidades/", views.gerar_mensalidades_view, name="mensalidades"),
]
