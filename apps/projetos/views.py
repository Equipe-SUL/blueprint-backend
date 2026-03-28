import os
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db import transaction

from .models import Projeto, ArquivoUpload , ItemProjeto
from .serializers import UploadArquivoSerializer, ProjetoSerializer , ItemProjetoSerializer


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
    
    
    
class ItemProjetoView(APIView):
    def get(self, request, projeto_id):
        try:
            # 
            projeto = get_object_or_404(Projeto, id=projeto_id)
            itens = ItemProjeto.objects.filter(projeto=projeto).order_by('id')
            
            if not itens.exists():
                return Response(
                    {
                        "message": "Nenhum item encontrado para este projeto.",
                        "data": []   
                    }, 
                    status=status.HTTP_200_OK
                )
            
            serializer = ItemProjetoSerializer(itens, many=True)
            return Response(
                {
                    "message": "Itens encontrados com sucesso.",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    "error": f"Erro interno ao buscar no servidor: {str(e)}",
                    "data": []
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, projeto_id):
        # 1. Buscamos o projeto. Se não existir, já devolve um Erro 404.
        projeto = get_object_or_404(Projeto, id=projeto_id)
        
        # A IA deve nos enviar uma lista (JSON) com os itens.
        itens_data = request.data
        
        # Verificamos se realmente recebemos uma lista
        if not isinstance(itens_data, list):
            return Response(
                {"error": "O corpo da requisição deve ser uma lista de itens."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Injetamos o ID do projeto em cada item do JSON recebido 
        # para que o nosso Tradutor (Serializer) saiba a qual projeto eles pertencem. (CA.2)
        for item in itens_data:
            item['projeto'] = projeto.id

        # 3. Chamamos nosso tradutor! O 'many=True' avisa que é uma lista de vários itens.
        serializer = ItemProjetoSerializer(data=itens_data, many=True)

        if serializer.is_valid():
            try:
                # 4. AQUI ENTRA O SUPERPODER: Transação Atômica (RN.3)
                with transaction.atomic():
                    # Salva todos os itens no banco de uma vez só!
                    itens_salvos = serializer.save()

                    # 5. Descobrir de quais arquivos esses itens vieram para atualizar o status.
                    # Usamos um 'set' para pegar IDs únicos (caso vários itens sejam do mesmo arquivo).
                    arquivos_ids = set([item.arquivo.id for item in itens_salvos])
                    
                    # Atualiza todos os arquivos vinculados para 'processado'
                    ArquivoUpload.objects.filter(id__in=arquivos_ids).update(
                        status_processamento=ArquivoUpload.Status.PROCESSADO
                    )

                    # CA.3: Retornar 201 com a lista cadastrada
                    return Response(serializer.data, status=status.HTTP_201_CREATED)

            except Exception as e:
                # Se o banco der algum "tilt" no meio do processo, a transação desfaz TUDO
                # e nós caímos aqui, retornando um erro 500 sem dados pela metade (CA.4)
                return Response(
                    {"error": f"Erro interno ao salvar os itens: {str(e)}"}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            # Se o JSON enviado pela IA faltar algum campo obrigatório, barra aqui. (CA.4)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
