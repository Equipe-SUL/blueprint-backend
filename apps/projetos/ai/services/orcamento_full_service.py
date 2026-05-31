import json
import os
import logging
from dataclasses import asdict

logger = logging.getLogger(__name__)


def processar_orcamento(
    caminho_dxf: str,
    projeto_id: int = None,
    arquivo_id: int = None,
    metadados_obra: dict = None,
    taxa_bdi: float = 25.0,
) -> dict:
    """
    Executa o pipeline completo de geracao de orcamento SINAPI a partir de um DXF.

    Passos:
      1. CAD Engine (blocos, ambientes)
      2. dxf_core (dados estruturais)
      3. Adaptacao dos itens para orcamento
      4. Analise estrutural geometrica
      5. Matching SINAPI + estimativas CUB
      6. Calculo final com BDI
      7. Salvamento no banco (Memorial.orcamento_final)
      8. Exportacao PDF

    Retorna:
        dict com sucesso, orcamento, pdf_path, memorial_db_id, etc.
    """
    print("\n" + "=" * 70)
    print("[ORCAMENTO] Iniciando pipeline de orcamento SINAPI...")
    print("=" * 70)

    if not caminho_dxf or not os.path.isfile(caminho_dxf):
        return {"sucesso": False, "erro": f"Arquivo DXF nao encontrado: {caminho_dxf}"}

    metadados = dict(metadados_obra or {})
    metadados.setdefault("nome", "Obra")
    metadados.setdefault("localizacao", "Nao informada")
    metadados.setdefault("tipo_construcao", "Nao informado")
    metadados.setdefault("padrao_acabamento", "Nao informado")

    try:
        from apps.projetos.ai.cad.engine import process_dxf as cad_process
        from apps.projetos.ai.extracaocalculo.dxf_core import extrair_dxf
        from apps.projetos.ai.services.adapter import (
            adaptar_blocos_para_orcamento,
            adaptar_memorial_para_orcamento,
        )
        from apps.projetos.ai.cad.structural_analysis import (
            adaptar_analise_estrutural,
        )
        from apps.projetos.ai.services.orcamento_service import (
            gerar_sugestoes_orcamento,
            calcular_orcamento_final,
        )
        from apps.projetos.ai.services.export_orcamento import exportar_csv
    except Exception as e:
        return {"sucesso": False, "erro": f"Erro ao importar modulos: {e}"}

    # ── 1. CAD Engine ───────────────────────────────────────────────────
    print("\n1/5 - CAD ENGINE")
    try:
        cad_result = cad_process(caminho_dxf)
    except Exception as e:
        return {"sucesso": False, "erro": f"Falha no CAD Engine: {e}"}

    print(f"   Rooms: {len(cad_result.rooms)}")
    print(f"   Blocos: {len(cad_result.full_report.get('blocos_por_tipo', {})) if cad_result.full_report else 0}")
    print(f"   Stats OK: {cad_result.success}")

    # ── 2. Dados Estruturais ────────────────────────────────────────────
    print("\n2/5 - DADOS ESTRUTURAIS")
    try:
        memorial = extrair_dxf(caminho_dxf)

        def sanitize(obj):
            if isinstance(obj, dict):
                return {k: sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize(v) for v in obj]
            elif isinstance(obj, tuple):
                return tuple(sanitize(v) for v in obj)
            elif hasattr(obj, "item") and callable(obj.item):
                return obj.item()
            return obj

        dados_estruturais = sanitize(asdict(memorial))
    except Exception as e:
        return {"sucesso": False, "erro": f"Falha na extracao dxf_core: {e}"}

    blocos_cad = (
        adaptar_blocos_para_orcamento(cad_result.full_report or {})
        if cad_result.success
        else []
    )

    print(f"   Camadas dxf_core: {len(dados_estruturais.get('resumo_por_camada', {}))}")
    print(f"   Blocos CAD adaptados: {len(blocos_cad)}")

    # ── 3. Adaptar Itens para Orcamento ─────────────────────────────────
    print("\n3/5 - ADAPTACAO DE ITENS")
    itens_cad = adaptar_memorial_para_orcamento(dados_estruturais)

    itens_estruturais = adaptar_analise_estrutural(memorial)
    if itens_estruturais:
        tipos_estruturais = {i["type"] for i in itens_estruturais}
        itens_cad = [i for i in itens_cad if i["type"] not in tipos_estruturais]
        itens_cad.extend(itens_estruturais)

    ids_existentes = {i["id"] for i in itens_cad}
    for b in blocos_cad:
        if b["id"] not in ids_existentes:
            itens_cad.append(b)
            ids_existentes.add(b["id"])

    print(f"   Total itens para orcamento: {len(itens_cad)}")

    # ── 4. Gerar Sugestoes SINAPI ──────────────────────────────────────
    print("\n4/5 - MATCHING SINAPI")
    try:
        sugestoes = gerar_sugestoes_orcamento(itens_cad, usar_llm=True)
    except Exception as e:
        return {"sucesso": False, "erro": f"Falha ao gerar sugestoes SINAPI: {e}"}

    # ── 5. Calcular Orcamento Final ────────────────────────────────────
    print("\n5/5 - CALCULO FINAL")
    orcamento = calcular_orcamento_final(sugestoes, taxa_bdi=taxa_bdi)
    resumo = orcamento.get("resumo", {})

    print(f"   Itens orcados: {resumo.get('total_itens', 0)}")
    print(f"   Sem matching: {resumo.get('total_sem_itens', 0)}")
    print(f"   Subtotal: R$ {resumo.get('subtotal', 0):.2f}")
    print(f"   TOTAL: R$ {resumo.get('total_geral', 0):.2f}")

    # ── 6. Salvar no Banco (Memorial) ──────────────────────────────────
    memorial_db_id = None
    if projeto_id:
        try:
            from apps.projetos.models import Projeto, Memorial
            projeto = Projeto.objects.get(pk=projeto_id)
            memorial_obj = Memorial.objects.create(
                projeto=projeto,
                orcamento_final=orcamento,
            )
            memorial_db_id = memorial_obj.pk
            print(f"\n   Memorial salvo no banco: ID={memorial_db_id}")
        except Exception as e:
            logger.error(f"Erro ao salvar orcamento no banco: {e}")
            print(f"   Erro ao salvar no banco: {e}")

    # ── 7. Popular ItemProjeto ──────────────────────────────────────────
    if projeto_id and memorial_db_id:
        try:
            from apps.projetos.models import Projeto, ArquivoUpload, ItemProjeto

            projeto_obj = Projeto.objects.get(pk=projeto_id)
            arquivo_obj = None
            if arquivo_id:
                arquivo_obj = ArquivoUpload.objects.filter(pk=arquivo_id).first()

            import re

            def _limpar_descricao(item: dict) -> str:
                raw = item.get("sinapi_descricao", "")
                if raw.startswith("ESTIMATIVA CUB | "):
                    parts = raw.split(" | ")
                    return parts[1] if len(parts) >= 2 else raw
                m = re.search(r"Descrição:\s*(.*?)\s*\(Unidade:", raw)
                if m:
                    return m.group(1).strip()
                return raw or item.get("descricao_cad", "")

            itens_criados = 0
            # Itens com matching SINAPI
            for i in orcamento.get("itens", []):
                ItemProjeto.objects.create(
                    projeto=projeto_obj,
                    arquivo=arquivo_obj,
                    descricao=_limpar_descricao(i),
                    unidade=i.get("sinapi_unidade", "un"),
                    quantidade=i.get("quantidade", 0),
                    preco_unitario=i.get("preco_unitario", 0),
                    origem=ItemProjeto.Origem.SINAPI,
                    status_mapeamento="mapeado",
                )
                itens_criados += 1

            print(f"   Itens criados em ItemProjeto: {itens_criados}")
        except Exception as e:
            logger.error(f"Erro ao popular ItemProjeto: {e}")
            print(f"   Erro ao popular ItemProjeto: {e}")

    # ── 8. Gerar XLSX ─────────────────────────────────────────────────
    csv_path = None
    csv_filename = None
    try:
        from django.conf import settings

        media_root = getattr(settings, "MEDIA_ROOT", ".")
        csv_dir = os.path.join(media_root, "orcamentos")
        os.makedirs(csv_dir, exist_ok=True)

        nome_arquivo = metadados.get("nome", "obra").replace(" ", "_").lower()
        if memorial_db_id:
            csv_filename = f"orcamento_{memorial_db_id}_{nome_arquivo}.xlsx"
        else:
            import uuid
            csv_filename = f"orcamento_{uuid.uuid4().hex[:8]}_{nome_arquivo}.xlsx"

        csv_path = os.path.join(csv_dir, csv_filename)
        exportar_csv(sugestoes, orcamento, csv_path, metadados=metadados)

        print(f"   XLSX gerado: {csv_path} ({os.path.getsize(csv_path) / 1024:.1f} KB)")
    except Exception as e:
        logger.error(f"Erro ao gerar XLSX do orcamento: {e}")
        print(f"   Erro ao gerar XLSX: {e}")

    # ── Resumo Final ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RESUMO DO ORCAMENTO")
    print("=" * 70)
    print(f"   Memorial DB ID: {memorial_db_id}")
    print(f"   XLSX: {csv_path}")
    print(f"   Valor orcado: R$ {resumo.get('total_geral', 0):.2f}")

    sucesso = memorial_db_id is not None or csv_path is not None

    return {
        "sucesso": sucesso,
        "orcamento": orcamento,
        "sugestoes": sugestoes,
        "memorial_db_id": memorial_db_id,
        "csv_path": csv_path,
        "csv_filename": csv_filename,
        "resumo": resumo,
        "erro": None if sucesso else "Nao foi possivel salvar nem gerar planilha",
    }
