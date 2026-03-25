import os
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.shortcuts import get_object_or_404
from django.conf import settings

from .models import Projeto, ArquivoUpload
from .serializers import UploadArquivoSerializer, ProjetoSerializer


class ProjetosViewSet(viewsets.ModelViewSet):
    '''Exibindo todos os Projetos'''
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer


EXTENSOES_PERMITIDAS = ['.csv', '.xlsx', '.xls']
TAMANHO_MAX_MB = 10

# Create your views here.
def server_status(request):
    return HttpResponse("Servidor está ativo")

class UploadArquivoView(APIView):
    def get(self, request, projeto_id):
        projeto = get_object_or_404(Projeto, id=projeto_id)
        arquivos = ArquivoUpload.objects.filter(projeto=projeto)
        serializer = UploadArquivoSerializer(arquivos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, projeto_id):
        
        # Obter o projeto do models com base no ID fornecido
        projeto = get_object_or_404(Projeto, id=projeto_id)

        arquivo = request.FILES.get('arquivo')
        if not arquivo:
            return Response(
                {"error": "Nenhum arquivo enviado. Use o Campo de Arquivo."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar extensão do arquivo
        nome_arquivo = arquivo.name
        
        _, ext = os.path.splitext(nome_arquivo.lower())
        if ext not in EXTENSOES_PERMITIDAS:
            return Response(
                {"error": f"Extensão '{ext}' não é permitida. Extensões permitidas: {', '.join(EXTENSOES_PERMITIDAS)}."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Checar o tamanho do arquivo
        tamanho_mb = arquivo.size / (1024 * 1024)   
        if tamanho_mb > TAMANHO_MAX_MB:
            return Response(
                {
                    "erro": (
                        f"Arquivo muito grande: {tamanho_mb:.2f} MB. "
                        f"Máximo permitido: {TAMANHO_MAX_MB} MB."
                    )
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        # Salvar o arquivo no sistema de arquivos local (futuramente num armazenamento em nuvem).
        try:
            directory = os.path.join(settings.MEDIA_ROOT, 'uploads', str(projeto_id))
            os.makedirs(directory, exist_ok=True)
            caminho_arquivo = os.path.join(directory, nome_arquivo)

            # chunks() escreve em pedaços (para não sobrecarregar a RAM)
            with open(caminho_arquivo, 'wb+') as destino:
                for chunk in arquivo.chunks():
                    destino.write(chunk)
        
        except Exception as e:
            return Response(
                {"error": f"Erro ao salvar o arquivo: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        arquivo_upload = ArquivoUpload.objects.create(
            projeto=projeto,
            nome_original=nome_arquivo,
            caminho_arquivo=caminho_arquivo,
            tamanho_mb=round(tamanho_mb, 2),
            status_processamento=ArquivoUpload.Status.PENDENTE,
        )

        serializer = UploadArquivoSerializer(arquivo_upload)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
