from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics
from rest_framework.permissions import AllowAny
from .serializers import RegistroSerializer
from django.contrib.auth.models import User 

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


class RegistroView(generics.CreateAPIView):
    queryset = User.objects.all()           
    permission_classes = (AllowAny,)         
    serializer_class = RegistroSerializer