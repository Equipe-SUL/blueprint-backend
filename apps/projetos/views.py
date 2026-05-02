from rest_framework import viewsets, status, parsers
from rest_framework.response import Response
from rest_framework.views import APIView

# Importamos apenas o essencial para não quebrar
from .models import Projeto
from .serializers import ProjetoSerializer

def server_status(request):
    from django.http import JsonResponse
    return JsonResponse({"status": "online"})

class ProjetosViewSet(viewsets.ModelViewSet):
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer

class UploadArquivoView(APIView):
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    def post(self, request, projeto_id):
        return Response({"message": "Upload realizado"}, status=status.HTTP_201_CREATED)

class ItemProjetoView(APIView):
    def get(self, request, projeto_id):
        return Response({"itens": []})

class TesteUploadPlanilhaView(APIView):
    def post(self, request, projeto_id):
        return Response({"status": "teste concluído"})