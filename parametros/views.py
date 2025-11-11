from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from .models import ParametroContrato
from .forms import ParametroContratoForm

def is_diretor_ou_admin(user):
    return hasattr(user, "funcionario") and user.funcionario.cargo in ["DIR", "ADMIN"]

# 🧾 LISTA DE CONTRATOS
@login_required
@user_passes_test(is_diretor_ou_admin)
def listar_contratos(request):
    contratos = ParametroContrato.objects.all().order_by("nome")
    return render(request, "parametros/listar_contratos.html", {"contratos": contratos})

# 📝 EDIÇÃO INDIVIDUAL
@login_required
@user_passes_test(is_diretor_ou_admin)
def editar_contrato(request, pk):
    contrato = get_object_or_404(ParametroContrato, pk=pk)
    form = ParametroContratoForm(instance=contrato)

    if request.method == "POST":
        form = ParametroContratoForm(request.POST, instance=contrato)
        if form.is_valid():
            form.save()
            messages.success(request, "Contrato atualizado com sucesso.")
            return redirect("parametros:listar_contratos")

    return render(request, "parametros/editar_contrato.html", {"form": form, "contrato": contrato})


@login_required
@user_passes_test(is_diretor_ou_admin)
def criar_contrato(request):
    from .forms import ParametroContratoForm
    form = ParametroContratoForm()

    if request.method == "POST":
        form = ParametroContratoForm(request.POST)
        if form.is_valid():
            contrato = form.save()
            messages.success(request, f"Contrato '{contrato.nome}' criado com sucesso.")
            return redirect("parametros:listar_contratos")

    return render(request, "parametros/editar_contrato.html", {"form": form, "contrato": None})
