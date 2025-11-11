from django.contrib import admin
from django.urls import path,include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from .views import home


urlpatterns = [
    path('admin/', admin.site.urls),
    path("", home, name="home"),

    #path('', login_required(TemplateView.as_view(template_name='home.html')), name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path("", include("django.contrib.auth.urls")),  # fornece /login, /logout, etc.
    path("", include(("clientes.urls", "clientes"), namespace="clientes")),
    path("", include(("condominios.urls", "condominios"), namespace="condominios")),
    path("", include(("funcionarios.urls", "funcionarios"), namespace="funcionarios")),
    path("", include(("modalidades.urls", "modalidades"), namespace="modalidades")),
    path("", include(("turmas.urls", "turmas"), namespace="turmas")),
    path("", include(("financeiro.urls", "financeiro"), namespace="financeiro")),
    path("parametros/", include("parametros.urls")),

    # home
    
    
]