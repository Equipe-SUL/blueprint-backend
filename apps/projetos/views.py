from rest_framework import viewsets
from apps.projetos.models import Projeto
from apps.projetos.serializer import ProjetoSerializer


class ProjetosViewSet(viewsets.ModelViewSet):
    '''Exibindo todos os Projetos'''
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer
