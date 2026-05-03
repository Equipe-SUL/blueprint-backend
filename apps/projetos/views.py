import os
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import viewsets, status, parsers
from rest_framework.response import Response
from rest_framework.views import APIView

# Importamos apenas o essencial para não quebrar
from .models import Projeto, ArquivoUpload
from .serializers import ProjetoSerializer, UploadArquivoSerializer

def server_status(request):
    from django.http import JsonResponse
    return JsonResponse({"status": "online"})

class ProjetosViewSet(viewsets.ModelViewSet):
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer

class UploadArquivoView(APIView):
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, projeto_id):
        # 1. Verificar se o projeto existe
        try:
            projeto = Projeto.objects.get(pk=projeto_id)
        except Projeto.DoesNotExist:
            return Response(
                {"erro": f"Projeto {projeto_id} não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. Verificar se o arquivo foi enviado
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            return Response(
                {"erro": "Nenhum arquivo enviado. Envie o campo 'arquivo' como form-data."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Salvar o arquivo em media/projetos/<id>/<nome>
        caminho_relativo = os.path.join("projetos", str(projeto_id), arquivo.name)
        caminho_salvo = default_storage.save(caminho_relativo, arquivo)

        # 4. Calcular tamanho em MB
        tamanho_mb = Decimal(arquivo.size) / Decimal(1024 * 1024)
        tamanho_mb = round(tamanho_mb, 2)

        # 5. Criar registro no banco (Supabase)
        registro = ArquivoUpload.objects.create(
            projeto=projeto,
            nome_original=arquivo.name,
            caminho_arquivo=caminho_salvo,
            tamanho_mb=tamanho_mb,
            status_processamento=ArquivoUpload.Status.PENDENTE,
        )

        # 6. Retornar dados do arquivo salvo
        serializer = UploadArquivoSerializer(registro)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ItemProjetoView(APIView):
    def get(self, request, projeto_id):
        return Response({"itens": []})

class TesteUploadPlanilhaView(APIView):
    def post(self, request, projeto_id):
        return Response({"status": "teste concluído"})