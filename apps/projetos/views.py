import os
import tempfile
from decimal import Decimal

from rest_framework import viewsets, status, parsers
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Projeto, ArquivoUpload, Memorial
from .serializers import ProjetoSerializer, UploadArquivoSerializer, MemorialSerializer

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

        # 3. Calcular tamanho em MB
        tamanho_mb = Decimal(arquivo.size) / Decimal(1024 * 1024)
        tamanho_mb = round(tamanho_mb, 2)

        # 4. Criar registro no banco (Supabase)
        registro = ArquivoUpload.objects.create(
            projeto=projeto,
            nome_original=arquivo.name,
            tamanho_mb=tamanho_mb,
            status_processamento=ArquivoUpload.Status.PENDENTE,
        )

        # 5. Inicializar a resposta base
        resposta = UploadArquivoSerializer(registro).data

        # 6. Se for DXF, processar via pipeline usando arquivo temporário
        if arquivo.name.lower().endswith('.dxf'):
            try:
                from apps.projetos.ai.services.pipeline_service import processar_dxf_completo

                # Salva em arquivo temporário para processamento
                sufixo = os.path.splitext(arquivo.name)[1]
                tmp = tempfile.NamedTemporaryFile(suffix=sufixo, delete=False)
                for chunk in arquivo.chunks():
                    tmp.write(chunk)
                tmp.close()  # No Windows, é obrigatório fechar antes de outra lib abrir
                caminho_temp = tmp.name

                try:
                    resultado_pipeline = processar_dxf_completo(caminho_temp, projeto_id)
                finally:
                    # Remove o arquivo temporário após processamento
                    os.unlink(caminho_temp)
                    # Remove também o .geojson gerado (mesmo nome, extensão diferente)
                    geojson_temp = caminho_temp.rsplit('.', 1)[0] + '.geojson'
                    if os.path.exists(geojson_temp):
                        os.unlink(geojson_temp)

                if resultado_pipeline.get("sucesso"):
                    # Cria o memorial na tabela separada
                    memorial = Memorial.objects.create(
                        projeto=projeto,
                        arquivo=registro,
                        memorial_calculo=resultado_pipeline.get("memorial_calculo"),
                        orcamento_final=resultado_pipeline.get("orcamento_final"),
                    )
                    registro.status_processamento = ArquivoUpload.Status.PROCESSADO
                    registro.save()
                    resposta["status_processamento"] = "processado"
                elif resultado_pipeline.get("pausado"):
                    # Pipeline pausado — aguardando decisão humana (HITL)
                    registro.status_processamento = ArquivoUpload.Status.PENDENTE
                    registro.save()
                    resposta["status_processamento"] = "aguardando_revisao"
                    resposta["thread_id"] = resultado_pipeline.get("thread_id")
                    resposta["interrupt_info"] = resultado_pipeline.get("interrupt_info")
                    resposta["alertas"] = resultado_pipeline.get("alertas", [])
                else:
                    registro.status_processamento = ArquivoUpload.Status.ERRO
                    registro.save()
                    resposta["status_processamento"] = "erro"
                    resposta["erro_pipeline"] = resultado_pipeline.get("erro", "Erro desconhecido no pipeline.")

            except Exception as e:
                import traceback
                traceback.print_exc()
                registro.status_processamento = ArquivoUpload.Status.ERRO
                registro.save()
                resposta["status_processamento"] = "erro"
                resposta["erro_pipeline"] = f"Exceção: {str(e)}"

        # 7. Se gerou memorial, inclui na resposta
        memoriais = Memorial.objects.filter(arquivo=registro)
        if memoriais.exists():
            resposta["memorial"] = MemorialSerializer(memoriais.first()).data

        return Response(resposta, status=status.HTTP_201_CREATED)

class ItemProjetoView(APIView):
    def get(self, request, projeto_id):
        return Response({"itens": []})


class RetomarPipelineView(APIView):
    """
    Endpoint para retomar um pipeline pausado por human-in-the-loop.

    POST /api/projetos/<projeto_id>/retomar/
    Body JSON: {"thread_id": "...", "decisao": "continuar" | "cancelar"}
    """

    def post(self, request, projeto_id):
        # 1. Verificar se o projeto existe
        try:
            projeto = Projeto.objects.get(pk=projeto_id)
        except Projeto.DoesNotExist:
            return Response(
                {"erro": f"Projeto {projeto_id} não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. Extrair parâmetros
        thread_id = request.data.get("thread_id")
        decisao = request.data.get("decisao", "continuar")

        if not thread_id:
            return Response(
                {"erro": "Campo 'thread_id' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if decisao not in ("continuar", "cancelar"):
            return Response(
                {"erro": "Campo 'decisao' deve ser 'continuar' ou 'cancelar'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Retomar o pipeline
        try:
            from apps.projetos.ai.services.pipeline_service import retomar_pipeline

            resultado = retomar_pipeline(thread_id, decisao)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {"erro": f"Erro ao retomar pipeline: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 4. Processar resultado
        resposta = {"projeto_id": projeto_id, "decisao": decisao}

        if resultado.get("sucesso"):
            # Busca o último arquivo pendente do projeto para criar o memorial
            arquivo_pendente = ArquivoUpload.objects.filter(
                projeto=projeto,
                status_processamento=ArquivoUpload.Status.PENDENTE,
            ).order_by("-enviado_em").first()

            memorial = Memorial.objects.create(
                projeto=projeto,
                arquivo=arquivo_pendente,
                memorial_calculo=resultado.get("memorial_calculo"),
                orcamento_final=resultado.get("orcamento_final"),
            )

            if arquivo_pendente:
                arquivo_pendente.status_processamento = ArquivoUpload.Status.PROCESSADO
                arquivo_pendente.save()

            resposta["sucesso"] = True
            resposta["memorial"] = MemorialSerializer(memorial).data
        else:
            resposta["sucesso"] = False
            resposta["erro"] = resultado.get("erro", "Pipeline não concluído.")
            resposta["alertas"] = resultado.get("alertas", [])

        return Response(resposta, status=status.HTTP_200_OK)


class TesteUploadPlanilhaView(APIView):
    def post(self, request, projeto_id):
        return Response({"status": "teste concluído"})