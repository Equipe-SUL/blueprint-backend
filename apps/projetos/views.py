import os
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from django.conf import settings

from rest_framework import viewsets, status, parsers
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Projeto, ArquivoUpload, Memorial, ItemProjeto
from .serializers import ProjetoSerializer, UploadArquivoSerializer, MemorialSerializer, ItemProjetoSerializer

def server_status(request):
    from django.http import JsonResponse
    return JsonResponse({"status": "online"})

class ProjetosViewSet(viewsets.ModelViewSet):
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer

class UploadArquivoView(APIView):
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get(self, request, projeto_id):
        projeto = get_object_or_404(Projeto, id=projeto_id)
        # 1. Checar arquivo físico existe em média: se não existir mais, se não existir excluir do banco
        for arquivo in projeto.arquivos.all():
            if arquivo.caminho_arquivo and not default_storage.exists(arquivo.caminho_arquivo):
                arquivo.delete()

        arquivos = projeto.arquivos.order_by("-enviado_em")
        serializer = UploadArquivoSerializer(arquivos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


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

        # 3. Calcular tamanho em MB e Salvar o arquivo em media/projetos/<id>/<nome>
        tamanho_mb = Decimal(arquivo.size) / Decimal(1024 * 1024)
        tamanho_mb = round(tamanho_mb, 2)

        caminho_relativo = os.path.join("projetos", str(projeto_id), arquivo.name)
        if default_storage.exists(caminho_relativo):
            return Response(
                {"erro": f"Arquivo '{arquivo.name}' já existe para este projeto."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        caminho_salvo = default_storage.save(caminho_relativo, arquivo)

        # 4. Criar registro no banco (Supabase)
        try:
            registro = ArquivoUpload.objects.create(
                projeto=projeto,
                nome_original=arquivo.name,
                tamanho_mb=tamanho_mb,
                caminho_arquivo=caminho_salvo,
                status_processamento=ArquivoUpload.Status.PENDENTE,
            )
        except Exception as e:
            # Se falhou ao criar registro, remove o arquivo salvo para evitar órfãos
            default_storage.delete(caminho_salvo)
            return Response(
                {"erro": f"Erro ao salvar registro do arquivo no banco: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        resposta = UploadArquivoSerializer(registro).data
        return Response(resposta, status=status.HTTP_201_CREATED)

    def delete(self, request, projeto_id, arquivo_id):
        # Validação: só remove se pertence ao projeto informado
        projeto = get_object_or_404(Projeto, id=projeto_id)
        arquivo = get_object_or_404(ArquivoUpload, id=arquivo_id, projeto=projeto)

        # Remove o arquivo físico apenas se ele ainda existir no storage.
        if arquivo.caminho_arquivo and default_storage.exists(arquivo.caminho_arquivo):
            try:
                default_storage.delete(arquivo.caminho_arquivo)
            except Exception as e:
                return Response(
                    {"erro": f"Erro ao remover arquivo do storage: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Remove registro do banco
        arquivo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)




class ProcessarArquivoView(APIView):
    """
    Endpoint para processar um arquivo já upado e gerar o documento (memorial).

    POST /api/projetos/<projeto_id>/processar/<arquivo_id>/
    Body JSON (opcional):
      - use_cad_engine: bool (default false)
      - tipo_construcao: str
      - padrao_acabamento: str
    """

    def post(self, request, projeto_id, arquivo_id):
        projeto = get_object_or_404(Projeto, id=projeto_id)
        arquivo = get_object_or_404(ArquivoUpload, id=arquivo_id, projeto=projeto)

        if not arquivo.caminho_arquivo:
            return Response(
                {"erro": "Arquivo não possui caminho físico registrado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not arquivo.nome_original.lower().endswith(".dxf"):
            return Response(
                {"erro": "Formato não suportado. Apenas arquivos .DXF podem ser processados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        caminho_fisico = os.path.join(settings.MEDIA_ROOT, arquivo.caminho_arquivo)
        if not os.path.isfile(caminho_fisico):
            return Response(
                {"erro": f"Arquivo físico não encontrado em: {caminho_fisico}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dados_adicionais = {
            "tipo_construcao": request.data.get("tipo_construcao", ""),
            "padrao_acabamento": request.data.get("padrao_acabamento", ""),
        }

        use_cad = request.data.get("use_cad_engine", "false") in (True, "true", "1", "yes")

        try:
            from apps.projetos.ai.services.descritivo_service import processar_memorial_descritivo

            resultado_pipeline = processar_memorial_descritivo(
                caminho_dxf=caminho_fisico,
                projeto_id=projeto_id,
                metadados_obra=dados_adicionais,
                use_cad_engine=use_cad,
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Exceção ao processar pipeline: {str(e)}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        resposta = {
            "projeto_id": projeto_id,
            "arquivo_id": arquivo_id,
            "sucesso": resultado_pipeline.get("sucesso", False),
        }

        if resultado_pipeline.get("sucesso"):
            memorial_id = resultado_pipeline.get("memorial_db_id")
            if memorial_id:
                Memorial.objects.filter(id=memorial_id).update(arquivo=arquivo)

            arquivo.status_processamento = ArquivoUpload.Status.PROCESSADO
            arquivo.save()

            resposta["status_processamento"] = "processado"
            resposta["memorial_db_id"] = memorial_id
            resposta["pdf_path"] = resultado_pipeline.get("pdf_path")
            resposta["inconsistencias"] = resultado_pipeline.get("inconsistencias", [])
            resposta["confianca"] = resultado_pipeline.get("confianca")

            cad_geo = resultado_pipeline.get("cad_polygons_geojson")
            if cad_geo:
                resposta["cad_polygons_geojson"] = cad_geo
                resposta["cad_rooms"] = resultado_pipeline.get("cad_rooms", [])
                resposta["cad_adjacency"] = resultado_pipeline.get("cad_adjacency", {})

            memorial = Memorial.objects.filter(arquivo=arquivo).first()
            if memorial:
                resposta["memorial"] = MemorialSerializer(memorial).data

            return Response(resposta, status=status.HTTP_200_OK)
        else:
            arquivo.status_processamento = ArquivoUpload.Status.ERRO
            arquivo.save()

            resposta["status_processamento"] = "erro"
            resposta["erro"] = resultado_pipeline.get("erro", "Erro desconhecido no pipeline.")
            return Response(resposta, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


class ItemProjetoView(APIView):
    def get(self, request, projeto_id):
        projeto = get_object_or_404(Projeto, id=projeto_id)
        itens = ItemProjeto.objects.filter(projeto=projeto).order_by("-id")
        serializer = ItemProjetoSerializer(itens, many=True)
        return Response({"message": "Itens do projeto", "data": serializer.data})

    def post(self, request, projeto_id):
        projeto = get_object_or_404(Projeto, id=projeto_id)
        serializer = ItemProjetoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(projeto=projeto, origem=ItemProjeto.Origem.PROPRIO, status_mapeamento="pendente")
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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


class ServirMemorialPDFView(APIView):
    """
    GET /api/projetos/<projeto_id>/memorial/<memorial_id>/pdf/
    Retorna o arquivo PDF do memorial descritivo para visualização no frontend.
    """

    def get(self, request, projeto_id, memorial_id):
        projeto = get_object_or_404(Projeto, id=projeto_id)
        memorial = get_object_or_404(Memorial, id=memorial_id, projeto=projeto)

        nome_obra = projeto.nome_obra.replace(" ", "_").lower()
        pdf_filename = f"memorial_descritivo_{memorial.id}_{nome_obra}.pdf"
        pdf_path = os.path.join(settings.MEDIA_ROOT, "memoriais", "descritivo", pdf_filename)

        if not os.path.isfile(pdf_path):
            return Response(
                {"erro": f"PDF não encontrado: {pdf_filename}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        from django.http import FileResponse

        response = FileResponse(
            open(pdf_path, "rb"),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = f'inline; filename="{pdf_filename}"'
        return response


class GerarOrcamentoView(APIView):
    """
    Gera o orçamento SINAPI a partir de um arquivo DXF já upado
    e retorna o CSV como download.

    POST /api/projetos/<projeto_id>/gerar-orcamento/<arquivo_id>/
    """

    def post(self, request, projeto_id, arquivo_id):
        projeto = get_object_or_404(Projeto, id=projeto_id)
        arquivo = get_object_or_404(ArquivoUpload, id=arquivo_id, projeto=projeto)

        if not arquivo.caminho_arquivo:
            return Response(
                {"erro": "Arquivo não possui caminho físico registrado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not arquivo.nome_original.lower().endswith(".dxf"):
            return Response(
                {"erro": "Formato não suportado. Apenas arquivos .DXF podem ser processados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        caminho_fisico = os.path.join(settings.MEDIA_ROOT, arquivo.caminho_arquivo)
        if not os.path.isfile(caminho_fisico):
            return Response(
                {"erro": f"Arquivo físico não encontrado em: {caminho_fisico}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        metadados = {
            "nome": projeto.nome_obra,
            "localizacao": f"{projeto.cidade_obra}, {projeto.estado_obra}",
            "descricao": projeto.desc_obra,
        }

        taxa_bdi = float(request.data.get("taxa_bdi", projeto.taxa_bdi or 25.0))

        try:
            from apps.projetos.ai.services.orcamento_full_service import processar_orcamento

            resultado = processar_orcamento(
                caminho_dxf=caminho_fisico,
                projeto_id=projeto_id,
                arquivo_id=arquivo_id,
                metadados_obra=metadados,
                taxa_bdi=taxa_bdi,
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {
                    "sucesso": False,
                    "erro": f"Exceção ao gerar orçamento: {str(e)}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not resultado.get("sucesso"):
            arquivo.status_processamento = ArquivoUpload.Status.ERRO
            arquivo.save()
            return Response(
                {
                    "sucesso": False,
                    "erro": resultado.get("erro", "Erro desconhecido ao gerar orçamento."),
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        memorial_id = resultado.get("memorial_db_id")
        if memorial_id:
            Memorial.objects.filter(id=memorial_id).update(arquivo=arquivo)

        arquivo.status_processamento = ArquivoUpload.Status.PROCESSADO
        arquivo.save()

        xlsx_path = resultado.get("csv_path")
        xlsx_filename = resultado.get("csv_filename", f"orcamento_{projeto.nome_obra}.xlsx")

        from django.http import FileResponse

        if not xlsx_path or not os.path.isfile(xlsx_path):
            return Response(
                {"sucesso": False, "erro": "Arquivo gerado não encontrado no servidor."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response = FileResponse(
            open(xlsx_path, "rb"),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{xlsx_filename}"'
        return response


class ServirOrcamentoPDFView(APIView):
    """
    GET /api/projetos/<projeto_id>/orcamento/<memorial_id>/pdf/
    Retorna o arquivo PDF do orçamento para visualização no frontend.
    """

    def get(self, request, projeto_id, memorial_id):
        projeto = get_object_or_404(Projeto, id=projeto_id)
        memorial = get_object_or_404(Memorial, id=memorial_id, projeto=projeto)

        nome_obra = projeto.nome_obra.replace(" ", "_").lower()
        pdf_filename = f"orcamento_{memorial.id}_{nome_obra}.pdf"
        pdf_path = os.path.join(settings.MEDIA_ROOT, "memoriais", "orcamento", pdf_filename)

        if not os.path.isfile(pdf_path):
            return Response(
                {"erro": f"PDF do orçamento não encontrado: {pdf_filename}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        from django.http import FileResponse

        response = FileResponse(
            open(pdf_path, "rb"),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = f'inline; filename="{pdf_filename}"'
        return response


class ExportarMateriaisView(APIView):
    """
    Gera um .xlsx com os itens de material (ItemProjeto) do projeto.

    GET /api/projetos/<projeto_id>/exportar-materiais/
    """

    def get(self, request, projeto_id):
        projeto = get_object_or_404(Projeto, id=projeto_id)
        itens = ItemProjeto.objects.filter(projeto=projeto)

        if not itens.exists():
            return Response(
                {"erro": "Nenhum material encontrado para exportar."},
                status=status.HTTP_404_NOT_FOUND,
            )

        sugestoes = []
        itens_orcados = []
        subtotal = 0.0

        for idx, item in enumerate(itens):
            preco = float(item.preco_unitario)
            qtd = float(item.quantidade)
            total = round(qtd * preco, 2)
            subtotal += total

            opcao = {
                "codigo": "",
                "descricao": item.descricao,
                "unidade": item.unidade,
                "preco_unitario": preco,
                "_selecionado": True,
            }

            sugestoes.append({
                "id_cad": str(item.id),
                "item_original": item.descricao,
                "quantidade": qtd,
                "unidade": item.unidade,
                "tipo": item.origem,
                "selecao_automatica": 0,
                "opcoes_sinapi": [opcao],
            })

            itens_orcados.append({
                "id_cad": str(item.id),
                "descricao_cad": item.descricao,
                "sinapi_codigo": "",
                "sinapi_descricao": item.descricao,
                "sinapi_unidade": item.unidade,
                "quantidade": qtd,
                "preco_unitario": preco,
                "custo_total": total,
                "selecionado_por_llm": True,
            })

        orcamento = {
            "itens": itens_orcados,
            "resumo": {
                "total_itens": len(itens_orcados),
                "total_sem_itens": 0,
                "subtotal": subtotal,
                "taxa_bdi_percentual": 0,
                "valor_bdi": 0,
                "total_geral": subtotal,
            },
        }

        metadados = {
            "nome": projeto.nome_obra,
            "localizacao": f"{projeto.cidade_obra}, {projeto.estado_obra}",
        }

        try:
            from apps.projetos.ai.services.export_orcamento import exportar_csv
            from django.conf import settings

            nome_arquivo = f"materiais_{projeto.nome_obra.replace(' ', '_').lower()}.xlsx"
            output_dir = os.path.join(settings.MEDIA_ROOT, "exportacoes")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, nome_arquivo)

            exportar_csv(sugestoes, orcamento, output_path, metadados=metadados)

            from django.http import FileResponse

            response = FileResponse(
                open(output_path, "rb"),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
            return response
        except Exception as e:
            return Response(
                {"erro": f"Erro ao gerar planilha: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TesteUploadPlanilhaView(APIView):
    def post(self, request, projeto_id):
        return Response({"status": "teste concluído"})