# turmas/urls.py
from django.urls import path
from . import views
from . import views_presenca

app_name = "turmas"

urlpatterns = [
    # Turmas
    path("turmas/", views.list_turmas, name="list"),
    path("turmas/criar/", views.create_turma, name="create"),
    path("turmas/<int:pk>/atualizar/", views.update_turma, name="update"),
    path("turmas/exportar/", views.exportar_view, name="exportar"),
    path("turmas/<int:turma_id>/alunos/", views.alunos_turma, name="alunos"),
    path("turmas/matricular/", views.matricular_view, name="matricular"),

    # Desmatricular (ESSA É A NOVA ROTA)
    path(
        "turmas/matriculas/<int:matricula_id>/desmatricular/",
        views.desmatricular_view,
        name="desmatricular",
    ),

    # Presenças
    path("turmas/<int:turma_id>/presencas/", views_presenca.listas_da_turma, name="presencas_turma"),
    path("turmas/presencas/criar/", views_presenca.criar_lista_presenca_view, name="presenca_criar"),
    path("turmas/presencas/auto/", views_presenca.gerar_listas_automaticas_view, name="presenca_auto"),
    path("turmas/presencas/<int:lista_id>/", views_presenca.presenca_detalhe, name="presenca_detalhe"),
    path("turmas/presencas/<int:lista_id>/salvar/", views_presenca.presenca_salvar_view, name="presenca_salvar"),
    # turmas/urls.py (adicione esta rota)
    path("turmas/<int:turma_id>/selecionar-cliente/", views.selecionar_cliente, name="selecionar_cliente"),
    

]
