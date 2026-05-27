from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics
from django.contrib.auth.models import User
from .serializers import RegistroSerializer


@api_view(['GET'])
@permission_classes([AllowAny])  # endpoint de status permanece público
def users_status(request):
    return Response(
        {
            "status": "API de Usuários OK!",
            "endpoints": [
                "/api/users/status/",
                "/api/users/cadastro/",
                "/api/users/login/",
                "/api/users/token/refresh/",
            ]
        },
        status=status.HTTP_200_OK
    )


class RegistroView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegistroSerializer