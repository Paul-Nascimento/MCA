# turmas/urls.py
from django.urls import path
from . import views
from . import views_presenca

app_name = "turmas"

urlpatterns = [
    # Turmas
    path("turmas/", views.list_turmas, name="list"),
    path("turmas/criar/", views.create_turma, name="create"),
    path("turmas/<int:turma_id>/atualizar/", views.update_turma, name="update"),
    path("turmas/exportar/", views.exportar_turmas, name="exportar"),
    path("turmas/<int:turma_id>/alunos/", views.alunos_turma, name="alunos"),
    path("turmas/matricular/", views.matricular_view, name="matricular"),

    # Ativar/Desativar turma
    path("turmas/<int:turma_id>/status/", views.toggle_status, name="toggle_status"),

    # Desmatricular
    path(
        "turmas/matriculas/<int:matricula_id>/desmatricular/",
        views.desmatricular_view,
        name="desmatricular",
    ),

    # Selecionar cliente (usado antes da matrícula)
    path(
        "turmas/<int:turma_id>/selecionar-cliente/",
        views.selecionar_cliente,
        name="selecionar_cliente",
    ),

    # Presenças
    path("turmas/<int:turma_id>/presencas/", views_presenca.listas_da_turma, name="presencas_turma"),
    path("turmas/presencas/criar/", views_presenca.criar_lista_presenca_view, name="presenca_criar"),
    path("turmas/presencas/auto/", views_presenca.gerar_listas_automaticas_view, name="presenca_auto"),
    path("turmas/presencas/<int:lista_id>/", views_presenca.presenca_detalhe, name="presenca_detalhe"),
    path("turmas/presencas/<int:lista_id>/salvar/", views_presenca.presenca_salvar_view, name="presenca_salvar"),
    path(
        "turmas/presencas/<int:lista_id>/ocorrencia/",
        views_presenca.presenca_salvar_view,
        name="presenca_ocorrencia",
    ),

        path(
        "turmas/<int:turma_id>/matriculas/",
        views.matriculas_turma_view,
        name="matriculas_turma",
    ),
    path(
    "turmas/<int:turma_id>/matricular-direto/",
    views.matricular_cliente_direto,
    name="matricular_direto",
),

path("turmas/dependente/cadastrar/", views.cadastrar_dependente_view, name="cadastrar_dependente"),



    
    
]
