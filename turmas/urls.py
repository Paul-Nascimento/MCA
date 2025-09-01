from django.urls import path
from . import views

app_name = "turmas"

urlpatterns = [
    path("turmas/", views.list_turmas, name="list"),
    path("turmas/criar/", views.create_turma, name="create"),
    path("turmas/<int:pk>/atualizar/", views.update_turma, name="update"),
    path("turmas/matricular/", views.matricular_cliente_view, name="matricular"),

    path("turmas/exportar/", views.exportar_turmas_view, name="exportar"),
    path("turmas/<int:pk>/alunos/", views.turma_alunos, name="alunos"),
    path("turmas/matriculas/<int:matricula_id>/encerrar/", views.encerrar_matricula_view, name="encerrar_matricula"),
]


# --- acrescente rotas de presença ---
from . import views_presenca as pres

urlpatterns += [
    path("turmas/<int:turma_id>/presencas/", pres.listas_da_turma, name="presencas_turma"),
    path("turmas/presencas/criar/", pres.criar_lista_presenca_view, name="presenca_criar"),
    path("turmas/presencas/auto/", pres.gerar_listas_automaticas_view, name="presenca_auto"),
    path("turmas/presencas/<int:lista_id>/", pres.presenca_detalhe, name="presenca_detalhe"),
    path("turmas/presencas/<int:lista_id>/salvar/", pres.presenca_salvar_view, name="presenca_salvar"),
]
