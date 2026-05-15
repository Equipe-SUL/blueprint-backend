import asyncio
import os

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from ..models import Projeto, ArquivoUpload, ItemProjeto, CatalogoItem
from ..serializers import ItemProjetoSerializer

# Importações da IA do Blueprint-Backend
from apps.projetos.ai.services.pipeline_service import processar_dxf_completo

class ItemProjetoView(APIView):
    async def get(self, request, projeto_id):
        try:
            projeto = await asyncio.to_thread(get_object_or_404, Projeto, id=projeto_id)
            itens = await asyncio.to_thread(
                lambda: list(ItemProjeto.objects.filter(projeto=projeto).order_by('id'))
            )

            if not itens:
                return Response(
                    {"message": "Nenhum item encontrado para este projeto.", "data": []},
                    status=status.HTTP_200_OK
                )

            serializer = ItemProjetoSerializer(itens, many=True)
            return Response(
                {"message": "Itens encontrados com sucesso.", "data": serializer.data},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": f"Erro interno ao buscar no servidor: {str(e)}", "data": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def post(self, request, projeto_id):
        projeto = await asyncio.to_thread(get_object_or_404, Projeto, id=projeto_id)
        itens_data = request.data

        is_manual = isinstance(itens_data, dict)

        if is_manual:
            descricao = itens_data.get('descricao_original', '').strip()
            unidade = itens_data.get('unidade', '').strip()

            if descricao and unidade:
                item_catalogo, created = await asyncio.to_thread(
                    CatalogoItem.objects.get_or_create,
                    descricao=descricao, defaults={'unidade': unidade}
                )
                itens_data['catalogo'] = item_catalogo.id

            itens_data = [itens_data]

        elif not isinstance(itens_data, list):
            return Response(
                {"error": "O corpo da requisição deve ser um objeto (manual) ou uma lista de itens (IA)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        for item in itens_data:
            item['projeto'] = projeto.id

        serializer = ItemProjetoSerializer(data=itens_data, many=True)

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    origem_salvar = ItemProjeto.Origem.COTACAO_MANUAL if is_manual else ItemProjeto.Origem.SINAPI
                    itens_salvos = serializer.save(origem=origem_salvar)

                    arquivos_ids = set([item.arquivo.id for item in itens_salvos if getattr(item, 'arquivo', None)])
                    if arquivos_ids:
                        await asyncio.to_thread(
                            ArquivoUpload.objects.filter(id__in=arquivos_ids).update,
                            status_processamento=ArquivoUpload.Status.PROCESSADO
                        )

                    dados_retorno = serializer.data[0] if is_manual else serializer.data
                    return Response(dados_retorno, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response(
                    {"error": f"Erro interno ao salvar: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TesteUploadPlanilhaView(APIView):
    parser_classes = [MultiPartParser]

    async def post(self, request, projeto_id):
        projeto = await asyncio.to_thread(get_object_or_404, Projeto, id=projeto_id)
        arquivo_upload = request.FILES.get('arquivo')

        if not arquivo_upload:
            return Response({"erro": "Nenhum arquivo enviado."}, status=status.HTTP_400_BAD_REQUEST)

        nome_arquivo = arquivo_upload.name.lower()
        if not (nome_arquivo.endswith('.xls') or nome_arquivo.endswith('.xlsx')):
            return Response({"erro": "Envie apenas arquivos Excel (.xls ou .xlsx)"}, status=status.HTTP_400_BAD_REQUEST)

        caminho_salvamento = os.path.join(settings.MEDIA_ROOT, 'testes_excel', str(projeto.id), arquivo_upload.name)
        os.makedirs(os.path.dirname(caminho_salvamento), exist_ok=True)

        with open(caminho_salvamento, 'wb+') as destination:
            for chunk in arquivo_upload.chunks():
                destination.write(chunk)

        from ..services import extrair_dados_excel
        resultado = await asyncio.to_thread(extrair_dados_excel, caminho_salvamento)

        if resultado.get("sucesso"):
            return Response({
                "mensagem": "Planilha Excel processada com precisão!",
                "dados": resultado
            }, status=status.HTTP_200_OK)
        else:
            return Response({"erro": resultado.get("erro")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InterpretarArquivoDxfView(APIView):
    """
    Hibridização: Usa o pipeline do Blueprint-Backend para interpretar o DXF,
    mas retorna apenas os itens adaptados para a View de Itens.
    """
    async def post(self, request, projeto_id: int, arquivo_id: int):
        projeto, arquivo = await asyncio.gather(
            asyncio.to_thread(get_object_or_404, Projeto, id=projeto_id),
            asyncio.to_thread(get_object_or_404, ArquivoUpload, id=arquivo_id, projeto__id=projeto_id),
        )

        try:
            # Em vez de interpretar_itens_extraidos_dxf (que não existe mais),
            # usamos o pipeline completo do Blueprint-Backend
            resultado = await asyncio.to_thread(
                processar_dxf_completo,
                arquivo.caminho_arquivo,
                projeto_id=projeto.id
            )

            if not resultado.get("sucesso"):
                return Response(
                    {"error": f"Erro no processamento do DXF: {resultado.get('erro', 'erro desconhecido')}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    "projeto_id": projeto.id,
                    "arquivo_id": arquivo.id,
                    "nome_arquivo": arquivo.nome_original,
                    "ai": resultado.get("itens_adaptados", []),
                    "memorial_calculo": resultado.get("memorial_calculo"),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": f"Erro interno na interpretação: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
