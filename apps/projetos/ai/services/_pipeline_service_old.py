"""
pipeline_service.py
====================
Orquestrador do fluxo completo:
    DXF → GeoJSON → Memorial de Cálculo → Adaptação → RAG → Memorial Orçamentário

Conecta a Etapa 1 (ExtraçãoCalculo) com a Etapa 2 (RAG + Orçamento SINAPI)
e salva ambos os memoriais em disco.
"""

import os
import sys
import json
from django.conf import settings

# Força o encoding UTF-8 no terminal do Windows para evitar erros com emojis
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dataclasses import asdict
from apps.projetos.ai.extracaocalculo.dxf_core import extrair_dxf

from apps.projetos.ai.services.adapter import adaptar_memorial_para_orcamento
from apps.projetos.ai.services.orcamento_service import (
    gerar_sugestoes_orcamento,
    calcular_orcamento_final,
)


def processar_dxf_completo(caminho_dxf: str, projeto_id: int = None) -> dict:
    """
    Pipeline completo: DXF → Memorial de Cálculo → RAG → Orçamento Final.

    Parâmetros:
        caminho_dxf : caminho absoluto do arquivo .dxf
        projeto_id  : ID do projeto no Supabase (para organizar os arquivos)

    Retorna:
        dict com:
          - sucesso: bool
          - memorial_calculo: JSON da Etapa 1
          - itens_adaptados: JSON intermediário (contrato de dados)
          - sugestoes_rag: sugestões SINAPI do RAG
          - orcamento_final: orçamento calculado com custos e BDI
          - caminhos: paths dos arquivos salvos
    """

    # ── ETAPA 1: Extração Direta do DXF ──────────────────────────────────
    print("\n[PIPELINE] Etapa 1: Extraindo geometria diretamente do DXF...")
    try:
        memorial_obj = extrair_dxf(caminho_dxf)
        # Converte o dataclass para dicionário para manter compatibilidade
        memorial_calculo = asdict(memorial_obj)
    except Exception as e:
        return {"sucesso": False, "erro": f"Falha na extração DXF: {e}"}

    # ── ADAPTADOR: Memorial → Formato Etapa 2 ────────────────────────────
    print("[PIPELINE] Adaptando JSON para formato do orçamento...")
    itens_adaptados = adaptar_memorial_para_orcamento(memorial_calculo)

    if not itens_adaptados:
        return {
            "sucesso": False,
            "erro": "Nenhum item estrutural encontrado no DXF.",
            "memorial_calculo": memorial_calculo,
        }

    print(f"[PIPELINE] {len(itens_adaptados)} itens adaptados para o RAG.")

    # ── ETAPA 2a: RAG - Busca de sugestões SINAPI ────────────────────────
    print("[PIPELINE] Etapa 2a: Buscando correspondências SINAPI via RAG...")
    try:
        sugestoes_rag = gerar_sugestoes_orcamento(itens_adaptados)
    except Exception as e:
        return {
            "sucesso": False,
            "erro": f"Falha na busca RAG/orçamento: {e}",
            "memorial_calculo": memorial_calculo,
            "itens_adaptados": itens_adaptados,
        }

    # ── ETAPA 2b: Cálculo orçamentário (quantidade × preço + BDI) ────────
    print("[PIPELINE] Etapa 2b: Calculando orçamento final...")

    # Busca taxa BDI do projeto no banco
    taxa_bdi = 0.0
    if projeto_id:
        try:
            from apps.projetos.models import Projeto

            projeto = Projeto.objects.get(pk=projeto_id)
            taxa_bdi = float(projeto.taxa_bdi)
            print(f"[PIPELINE] Taxa BDI do projeto: {taxa_bdi}%")
        except Exception:
            print("[PIPELINE] Projeto não encontrado, BDI = 0%")

    orcamento_final = calcular_orcamento_final(
        sugestoes=sugestoes_rag,
        selecoes=None,  # Usa a primeira opção SINAPI por padrão
        taxa_bdi=taxa_bdi,
    )

    print(
        f"[PIPELINE] Orçamento: {orcamento_final['resumo']['total_itens']} itens | "
        f"Subtotal: R$ {orcamento_final['resumo']['subtotal']:.2f} | "
        f"BDI: R$ {orcamento_final['resumo']['valor_bdi']:.2f} | "
        f"TOTAL: R$ {orcamento_final['resumo']['total_geral']:.2f}"
    )

    print("[PIPELINE] Fluxo completo finalizado com sucesso!")

    return {
        "sucesso": True,
        "memorial_calculo": memorial_calculo,
        "itens_adaptados": itens_adaptados,
        "sugestoes_rag": sugestoes_rag,
        "orcamento_final": orcamento_final,
    }
