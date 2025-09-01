from django.urls import path
from . import views

app_name = "modalidades"

urlpatterns = [
    path("modalidades/", views.list_modalidades, name="list"),
    path("modalidades/criar/", views.create_modalidade, name="create"),
    path("modalidades/<int:pk>/atualizar/", views.update_modalidade, name="update"),
]
