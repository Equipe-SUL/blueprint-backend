import os
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db import transaction

from rest_framework.parsers import MultiPartParser
from .services import extrair_dados_dxf, extrair_dados_excel


from .models import Projeto, ArquivoUpload , ItemProjeto
from .serializers import UploadArquivoSerializer, ProjetoSerializer , ItemProjetoSerializer

class ProjetosViewSet(viewsets.ModelViewSet):
    '''Exibindo todos os Projetos'''
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer

EXTENSOES_PERMITIDAS = ['.dxf', '.xlsx', '.xls'] #['.csv', '.xlsx', '.xls']
TAMANHO_MAX_MB = 15

def server_status(request):    return HttpResponse("Servidor está ativo")

# =====================================================================
# INÍCIO DO BLOCO DXF 
# -> Esta View (UploadArquivoView) lida exclusivamente com arquivos .dxf
# -> Se a equipe decidir usar apenas o fluxo Excel no futuro, toda esta 
#    classe pode ser removida (junto com a função extrair_dados_dxf no services.py).
# =====================================================================
class UploadArquivoView(APIView):
    # Necessário para lidar com form-data/arquivos via DRF
    parser_classes = [MultiPartParser]

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
                {"error": "Nenhum arquivo enviado. Use o Campo 'arquivo'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar extensão do arquivo (Bloqueado apenas para arquivos permitidos acima, na linha 22)
        nome_arquivo = arquivo.name
        _, ext = os.path.splitext(nome_arquivo.lower())
        if ext == '.dxf':
            extracao = extrair_dados_dxf(caminho_arquivo)
        elif ext in ['.xls', '.xlsx']:
            extracao = extrair_dados_excel(caminho_arquivo)
        else:
            return Response(
                {"error": "Formato de arquivo não suportado para extração."}, 
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

        # 1. Salvar o arquivo no sistema de arquivos local
        try:
            directory = os.path.join(settings.MEDIA_ROOT, 'uploads', str(projeto_id))
            os.makedirs(directory, exist_ok=True)
            caminho_arquivo = os.path.join(directory, nome_arquivo)

            with open(caminho_arquivo, 'wb+') as destino:
                for chunk in arquivo.chunks():
                    destino.write(chunk)
        
        except Exception as e:
            return Response(
                {"error": f"Erro ao salvar o arquivo fisicamente: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 2. Arquivo salvo. Acionando o Service de Extração EXCLUSIVO do DXF
        extracao = extrair_dados_dxf(caminho_arquivo)
        
        if not extracao["sucesso"]:
            return Response(
                {"error": f"Arquivo salvo, mas erro ao ler o DXF: {extracao['erro']}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 3. Criar registro do arquivo no banco de dados
        arquivo_upload = ArquivoUpload.objects.create(
            projeto=projeto,
            nome_original=nome_arquivo,
            caminho_arquivo=caminho_arquivo,
            tamanho_mb=round(tamanho_mb, 2),
            status_processamento=ArquivoUpload.Status.PROCESSADO, 
        )

        serializer = UploadArquivoSerializer(arquivo_upload)
        
        # 4. Retornar os dados do arquivo + os textos extraídos para o Front-end
        resposta_final = {
            "arquivo": serializer.data,
            "itens_extraidos": extracao["itens"]
        }
        
        return Response(resposta_final, status=status.HTTP_201_CREATED)
# =====================================================================
# FIM DO BLOCO DXF
# =====================================================================


# =====================================================================
# INÍCIO DO BLOCO DE ITENS DO PROJETO (CRUD BASE)
# -> Esta classe gerencia os itens já extraídos no banco de dados.
# -> DEVE SER MANTIDA, independente se a origem foi DXF ou Excel.
# =====================================================================
class ItemProjetoView(APIView):
    def get(self, request, projeto_id):
        try:
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
        projeto = get_object_or_404(Projeto, id=projeto_id)
        itens_data = request.data
        
        if not isinstance(itens_data, list):
            return Response(
                {"error": "O corpo da requisição deve ser uma lista de itens."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        for item in itens_data:
            item['projeto'] = projeto.id

        serializer = ItemProjetoSerializer(data=itens_data, many=True)

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    itens_salvos = serializer.save()

                    arquivos_ids = set([item.arquivo.id for item in itens_salvos if getattr(item, 'arquivo', None)])
                    if arquivos_ids:
                        ArquivoUpload.objects.filter(id__in=arquivos_ids).update(
                            status_processamento=ArquivoUpload.Status.PROCESSADO
                        )

                    return Response(serializer.data, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response(
                    {"error": f"Erro interno ao salvar os itens: {str(e)}"}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
# =====================================================================
# FIM DO BLOCO DE ITENS
# =====================================================================


# =====================================================================
# INÍCIO DO BLOCO EXCEL (PLANO B)
# -> Esta View (TesteUploadPlanilhaView) lida com as planilhas do AutoCAD (.xls/.xlsx).
# -> Este é o fluxo recomendado (mais preciso). Se a equipe decidir adotar 
#    este método oficialmente, esta classe deve ser mantida e aprimorada (ex: salvando no DB).
# =====================================================================
class TesteUploadPlanilhaView(APIView):
    # Necessário para lidar com form-data no Postman/Front-end
    parser_classes = [MultiPartParser]

    def post(self, request, projeto_id):
        # 1. Verifica se o projeto existe
        projeto = get_object_or_404(Projeto, id=projeto_id)
        arquivo_upload = request.FILES.get('arquivo')
        
        if not arquivo_upload:
            return Response({"erro": "Nenhum arquivo enviado."}, status=status.HTTP_400_BAD_REQUEST)
            
        # Aceita tanto .xls (AutoCAD antigo) quanto .xlsx (Novo)
        nome_arquivo = arquivo_upload.name.lower()
        if not (nome_arquivo.endswith('.xls') or nome_arquivo.endswith('.xlsx')):
             return Response({"erro": "Envie apenas arquivos Excel (.xls ou .xlsx)"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Salva o Excel na pasta temporária de testes
        caminho_salvamento = os.path.join(settings.MEDIA_ROOT, 'testes_excel', str(projeto.id), arquivo_upload.name)
        os.makedirs(os.path.dirname(caminho_salvamento), exist_ok=True)
        
        with open(caminho_salvamento, 'wb+') as destination:
            for chunk in arquivo_upload.chunks():
                destination.write(chunk)
                
        # 3. Chama a mágica do Pandas que criamos no services.py
        resultado = extrair_dados_excel(caminho_salvamento)
        
        if resultado.get("sucesso"):
            return Response({
                "mensagem": "Planilha Excel processada com precisão!",
                "dados": resultado
            }, status=status.HTTP_200_OK)
        else:
            return Response({"erro": resultado.get("erro")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# =====================================================================
# FIM DO BLOCO EXCEL
# =====================================================================