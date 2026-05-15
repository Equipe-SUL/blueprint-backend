from rest_framework import viewsets

from ..models import Projeto
from ..serializers import ProjetoSerializer


class ProjetosViewSet(viewsets.ModelViewSet):
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer
