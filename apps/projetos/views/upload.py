import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from ..models import Projeto, ArquivoUpload, Memorial
from ..serializers import UploadArquivoSerializer, MemorialSerializer

# Importações da IA do Blueprint-Backend
from apps.projetos.ai.services.pipeline_service import processar_dxf_completo, retomar_pipeline

EXTENSOES_PERMITIDAS = ['.dxf', '.xlsx', '.xls']
TAMANHO_MAX_MB = 15

_executor = ThreadPoolExecutor(max_workers=2)

class UploadArquivoView(APIView):
    parser_classes = [MultiPartParser]

    async def get(self, request, projeto_id):
        projeto = await asyncio.to_thread(get_object_or_404, Projeto, id=projeto_id)
        arquivos = await asyncio.to_thread(
            lambda: list(ArquivoUpload.objects.filter(projeto=projeto))
        )
        serializer = UploadArquivoSerializer(arquivos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    async def post(self, request, projeto_id):
        projeto = await asyncio.to_thread(get_object_or_404, Projeto, id=projeto_id)

        arquivo = request.FILES.get('arquivo')
        if not arquivo:
            return Response(
                {"error": "Nenhum arquivo enviado. Use o Campo 'arquivo'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        nome_arquivo = arquivo.name
        _, ext = os.path.splitext(nome_arquivo.lower())
        if ext not in EXTENSOES_PERMITIDAS:
            return Response(
                {"error": f"Formato '{ext}' não é permitida. Extensões permitidas: {', '.join(EXTENSOES_PERMITIDAS)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        tamanho_mb = arquivo.size / (1024 * 1024)
        if tamanho_mb > TAMANHO_MAX_MB:
            return Response(
                {"erro": f"Arquivo muito grande: {tamanho_mb:.2f} MB. Máximo permitido: {TAMANHO_MAX_MB} MB."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

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

        # 1. Registrar o upload no banco
        arquivo_upload = await asyncio.to_thread(
            ArquivoUpload.objects.create,
            projeto=projeto,
            nome_original=nome_arquivo,
            caminho_arquivo=caminho_arquivo,
            tamanho_mb=round(tamanho_mb, 2),
            status_processamento=ArquivoUpload.Status.PENDENTE,
        )

        resposta_final = {
            "arquivo": UploadArquivoSerializer(arquivo_upload).data,
        }

        # 2. Processamento Diferenciado
        if ext == '.dxf':
            try:
                # Executa o pipeline de IA no thread pool para não travar o loop async
                resultado_pipeline = await asyncio.to_thread(
                    processar_dxf_completo, caminho_arquivo, projeto.id
                )

                if resultado_pipeline.get("sucesso"):
                    # Cria o memorial na tabela separada
                    memorial = await asyncio.to_thread(
                        Memorial.objects.create,
                        projeto=projeto,
                        arquivo=arquivo_upload,
                        memorial_calculo=resultado_pipeline.get("memorial_calculo"),
                        orcamento_final=resultado_pipeline.get("orcamento_final"),
                    )
                    arquivo_upload.status_processamento = ArquivoUpload.Status.PROCESSADO
                    await asyncio.to_thread(arquivo_upload.save)

                    resposta_final["status_processamento"] = "processado"
                    resposta_final["memorial"] = MemorialSerializer(memorial).data

                elif resultado_pipeline.get("pausado"):
                    # Pipeline pausado — aguardando decisão humana (HITL)
                    arquivo_upload.status_processamento = ArquivoUpload.Status.PENDENTE
                    await asyncio.to_thread(arquivo_upload.save)

                    resposta_final["status_processamento"] = "aguardando_revisao"
                    resposta_final["thread_id"] = resultado_pipeline.get("thread_id")
                    resposta_final["interrupt_info"] = resultado_pipeline.get("interrupt_info")
                    resposta_final["alertas"] = resultado_pipeline.get("alertas", [])

                else:
                    arquivo_upload.status_processamento = ArquivoUpload.Status.ERRO
                    await asyncio.to_thread(arquivo_upload.save)
                    resposta_final["status_processamento"] = "erro"
                    resposta_final["erro_pipeline"] = resultado_pipeline.get("erro", "Erro desconhecido no pipeline.")

            except Exception as e:
                arquivo_upload.status_processamento = ArquivoUpload.Status.ERRO
                await asyncio.to_thread(arquivo_upload.save)
                resposta_final["status_processamento"] = "erro"
                resposta_final["erro_pipeline"] = f"Exceção: {str(e)}"

        elif ext in ['.xls', '.xlsx']:
            from ..services import extrair_dados_excel
            extracao = await asyncio.to_thread(extrair_dados_excel, caminho_arquivo)
            if extracao.get("sucesso"):
                arquivo_upload.status_processamento = ArquivoUpload.Status.PROCESSADO
                await asyncio.to_thread(arquivo_upload.save)
                resposta_final["itens_extraidos"] = extracao["itens"]
            else:
                arquivo_upload.status_processamento = ArquivoUpload.Status.ERRO
                await asyncio.to_thread(arquivo_upload.save)
                resposta_final["erro"] = extracao.get("erro")

        return Response(resposta_final, status=status.HTTP_201_CREATED)

class RetomarPipelineView(APIView):
    """
    Endpoint para retomar um pipeline pausado por human-in-the-loop.
    """
    async def post(self, request, projeto_id):
        projeto = await asyncio.to_thread(get_object_or_404, Projeto, id=projeto_id)

        thread_id = request.data.get("thread_id")
        decisao = request.data.get("decisao", "continuar")

        if not thread_id:
            return Response({"erro": "Campo 'thread_id' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

        if decisao not in ("continuar", "cancelar"):
            return Response({"erro": "Campo 'decisao' deve ser 'continuar' ou 'cancelar'."}, status=status.HTTP_400_BAD_ requester_400_BAD_REQUEST)

        try:
            resultado = await asyncio.to_thread(retomar_pipeline, thread_id, decisao)
        except Exception as e:
            return Response({"erro": f"Erro ao retomar pipeline: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        resposta = {"projeto_id": projeto_id, "decisao": decisao}

        if resultado.get("sucesso"):
            arquivo_pendente = await asyncio.to_thread(
                lambda: ArquivoUpload.objects.filter(
                    projeto=projeto,
                    status_processamento=ArquivoUpload.Status.PENDENTE,
                ).order_by("-enviado_em").first()
            )

            memorial = await asyncio.to_thread(
                Memorial.objects.create,
                projeto=projeto,
                arquivo=arquivo_pendente,
                memorial_calculo=resultado.get("memorial_calculo"),
                orcamento_final=resultado.get("orcamento_final"),
            )

            if arquivo_pendente:
                arquivo_pendente.status_processamento = ArquivoUpload.Status.PROCESSADO
                await asyncio.to_thread(arquivo_pendente.save)

            resposta["sucesso"] = True
            resposta["memorial"] = MemorialSerializer(memorial).data
        else:
            resposta["sucesso"] = False
            resposta["erro"] = resultado.get("erro", "Pipeline não concluído.")
            resposta["alertas"] = resultado.get("alertas", [])

        return Response(resposta, status=status.HTTP_200_OK)
