from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
def users_status(request):
    """
    Endpoint de status da API de usuarios.
    Serve como checagem minima de que o app foi configurado corretamente.
    As views de cadastro, login, refresh e logout entram depois.
    """
    return Response(
        {
            "status": "API de Usuários OK!",
            "endpoints": [
                "/api/users/status/",
                # Endpoints previstos para a task de autenticacao:
                # "/api/users/register/",
                # "/api/users/login/",
                # "/api/users/logout/",
            ]
        },
        status=status.HTTP_200_OK
    )
