import os
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db import transaction

from apps.projetos.services.conversor import converter_dxf_para_lista_itens

from .models import Projeto, ArquivoUpload , ItemProjeto
from .serializers import UploadArquivoSerializer, ProjetoSerializer , ItemProjetoSerializer


class ProjetosViewSet(viewsets.ModelViewSet):
    '''Exibindo todos os Projetos'''
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer


EXTENSOES_PERMITIDAS = ['.dxf']
TAMANHO_MAX_MB = 40

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
        projeto = get_object_or_404(Projeto, id=projeto_id)
        arquivo = request.FILES.get('arquivo')
        
        if not arquivo:
            return Response({"error": "Nenhum arquivo enviado."}, status=status.HTTP_400_BAD_REQUEST)
        
        nome_arquivo = arquivo.name
        _, ext = os.path.splitext(nome_arquivo.lower())
        
        if ext not in EXTENSOES_PERMITIDAS:
            return Response({"error": f"Extensão '{ext}' não permitida."}, status=status.HTTP_400_BAD_REQUEST)

        tamanho_mb = arquivo.size / (1024 * 1024)   
        if tamanho_mb > TAMANHO_MAX_MB:
            return Response({"error": "Arquivo muito grande."}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        try:
            directory = os.path.join(settings.MEDIA_ROOT, 'uploads', str(projeto_id))
            os.makedirs(directory, exist_ok=True)
            caminho_arquivo = os.path.join(directory, nome_arquivo)

            with open(caminho_arquivo, 'wb+') as destino:
                for chunk in arquivo.chunks():
                    destino.write(chunk)
        
            # Cria o registro no banco
            arquivo_upload = ArquivoUpload.objects.create(
                projeto=projeto,
                nome_original=nome_arquivo,
                caminho_arquivo=caminho_arquivo,
                tamanho_mb=round(tamanho_mb, 2),
                status_processamento=ArquivoUpload.Status.PENDENTE,
            )

            # --- PROCESSAMENTO ---
            # Se for DXF, processa e já retorna
            if ext == '.dxf':
                itens_json = converter_dxf_para_lista_itens(caminho_arquivo, arquivo_upload.id)
                serializer_arquivo = UploadArquivoSerializer(arquivo_upload)
                return Response({
                    "arquivo": serializer_arquivo.data,
                    "itens_para_lancar": itens_json
                }, status=status.HTTP_201_CREATED)
            
            # Se for outra extensão (CSV, XLS), retorna apenas os dados do arquivo
            serializer = UploadArquivoSerializer(arquivo_upload)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            print(traceback.format_exc()) # Isso vai imprimir o erro detalhado no seu terminal
            return Response({
                "error": f"Erro no processamento: {str(e)}",
                "traceback": traceback.format_exc() # Isso manda o erro detalhado para o Postman
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, projeto_id, arquivo_id):
        """remove um arquivo associado a um projeto. agora vai porra"""
        # Validação: só remove se pertence ao projeto informado
        projeto = get_object_or_404(Projeto, id=projeto_id)
        arquivo = get_object_or_404(ArquivoUpload, id=arquivo_id, projeto=projeto)

        # Remove arquivo físico (se existir)
        if arquivo.caminho_arquivo and os.path.exists(arquivo.caminho_arquivo):
            os.remove(arquivo.caminho_arquivo)

        # Remove registro do banco (remove vínculo do projeto automaticamente)
        arquivo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    
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