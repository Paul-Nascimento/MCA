# core/middleware.py
from django.shortcuts import redirect
from django.urls import reverse

class ProfessorRestrictionMiddleware:
    """
    Impede professores de acessarem rotas fora das turmas.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        # Só aplica a usuários autenticados
        if user.is_authenticated:
            # Checa se é professor (e não superuser)
            if user.groups.filter(name='Professor').exists() and not user.is_superuser:
                print('Erro')
                # Libera apenas caminhos permitidos
                allowed_prefixes = [
                    '/turmas',           # todas as rotas de turmas
                    '/static',           # arquivos estáticos
                    '/media',            # mídia (caso use)
                    '/accounts/logout',  # permitir logout
                    '/admin/logout',     # caso vá pelo admin
                ]

                # Se a rota não for permitida
                if not any(request.path.startswith(p) for p in allowed_prefixes):
                    return redirect(reverse('turmas:list'))

        return self.get_response(request)
