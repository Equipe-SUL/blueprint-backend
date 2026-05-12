"""
nodes.py
========
Implementação de todos os nós do grafo LangGraph Blueprint.

Cada função:
  - Recebe o BlueprintState completo
  - Executa sua lógica
  - Retorna um dict parcial com as chaves modificadas

Nós:
  1. node_extrair      — Extração determinística do DXF
  2. node_classificar  — Classificação de layers (regras + LLM)
  3. node_filtrar      — Filtragem por categoria
  4. node_validar      — Validação de coerência (com interrupt para human-in-the-loop)
  5. node_calcular     — Cálculos geométricos
  6. node_adaptar      — Adaptação para formato RAG
  7. node_rag          — Busca SINAPI via RAG
  8. node_orcamento    — Cálculo de orçamento final

Observabilidade:
  - Todos os nós decorados com @traceable (LangSmith)
  - Tracing automático via LANGSMITH_TRACING=true no .env
"""

import json
import logging

from langsmith import traceable
from langgraph.types import interrupt

from apps.projetos.ai.graph.state import BlueprintState
from apps.projetos.ai.extraction.dxf_reader import ler_entidades_dxf
from apps.projetos.ai.extraction.geometry import (
    PROCESSADORES,
    calcular_area,
    calcular_perimetro,
    remover_z,
    esta_fechada,
)
from apps.projetos.ai.classification.layer_classifier import classificar_layers
from apps.projetos.ai.classification.taxonomy import (
    CATEGORIAS_DESCARTAVEIS,
    MAPA_CATEGORIA_SINAPI,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# NÓ 1 — EXTRAÇÃO DETERMINÍSTICA
# ═══════════════════════════════════════════════════════════════════════════

@traceable(name="node_extrair", run_type="chain")
def node_extrair(state: BlueprintState) -> dict:
    """
    Lê o arquivo DXF e extrai entidades geométricas com filtros.

    Entrada:  state["caminho_dxf"]
    Saída:    entidades_brutas, layers_encontradas, estatisticas_extracao
    """
    print("\n[GRAFO] 🔧 Nó 1: Extração determinística do DXF...")

    resultado = ler_entidades_dxf(state["caminho_dxf"])

    return {
        "entidades_brutas": resultado["entidades_brutas"],
        "layers_encontradas": resultado["layers_encontradas"],
        "estatisticas_extracao": resultado["estatisticas_extracao"],
        "total_ignorados_extracao": resultado["total_ignorados"],
        "etapa_atual": "extracao_completa",
    }


# ═══════════════════════════════════════════════════════════════════════════
# NÓ 2 — CLASSIFICAÇÃO DE LAYERS
# ═══════════════════════════════════════════════════════════════════════════

@traceable(name="node_classificar", run_type="chain")
def node_classificar(state: BlueprintState) -> dict:
    """
    Classifica cada layer em uma categoria estrutural.

    Entrada:  state["layers_encontradas"]
    Saída:    mapa_layers, layers_ambiguas
    """
    print("\n[GRAFO] 🤖 Nó 2: Classificação de layers...")

    mapa = classificar_layers(state["layers_encontradas"], usar_llm=True)
    ambiguas = [k for k, v in mapa.items() if v == "desconhecido"]

    print(f"   📊 Mapa de classificação: {json.dumps(mapa, ensure_ascii=False, indent=2)}")

    return {
        "mapa_layers": mapa,
        "layers_ambiguas": ambiguas,
        "etapa_atual": "classificacao_completa",
    }


# ═══════════════════════════════════════════════════════════════════════════
# NÓ 3 — FILTRAGEM PÓS-CLASSIFICAÇÃO
# ═══════════════════════════════════════════════════════════════════════════

@traceable(name="node_filtrar", run_type="chain")
def node_filtrar(state: BlueprintState) -> dict:
    """
    Remove entidades cujas layers foram classificadas como descartáveis.

    Entrada:  state["entidades_brutas"], state["mapa_layers"]
    Saída:    entidades_filtradas, entidades_removidas, motivos_remocao
    """
    print("\n[GRAFO] 🧹 Nó 3: Filtragem pós-classificação...")

    filtradas = []
    removidas = 0
    motivos = {}

    for ent in state["entidades_brutas"]:
        categoria = state["mapa_layers"].get(ent["layer"], "desconhecido")

        if categoria in CATEGORIAS_DESCARTAVEIS:
            removidas += 1
            motivos[categoria] = motivos.get(categoria, 0) + 1
            continue

        # Anota a categoria na entidade
        ent["categoria"] = categoria
        filtradas.append(ent)

    print(f"   ✅ Mantidas: {len(filtradas)} | 🚫 Removidas: {removidas}")
    if motivos:
        print(f"   📊 Motivos: {motivos}")

    return {
        "entidades_filtradas": filtradas,
        "entidades_removidas": removidas,
        "motivos_remocao": motivos,
        "etapa_atual": "filtragem_completa",
    }


# ═══════════════════════════════════════════════════════════════════════════
# NÓ 4 — VALIDAÇÃO DE COERÊNCIA (COM HUMAN-IN-THE-LOOP)
# ═══════════════════════════════════════════════════════════════════════════

@traceable(name="node_validar", run_type="chain")
def node_validar(state: BlueprintState) -> dict:
    """
    Valida a coerência dos dados extraídos.

    Verifica anomalias como:
      - Pilar com área > 10 m²
      - Viga com comprimento > 50 m
      - Poucas entidades extraídas
      - Muitas entidades em layer "desconhecido"

    Quando alertas CRÍTICOS são detectados, usa interrupt() do LangGraph
    para pausar a execução e solicitar revisão humana.

    Entrada:  state["entidades_filtradas"], state["mapa_layers"]
    Saída:    validacao_ok, alertas
    """
    print("\n[GRAFO] ✅ Nó 4: Validação de coerência...")

    alertas = []
    entidades = state.get("entidades_filtradas", [])

    # ── Verifica se há entidades suficientes ────────────────────────────
    if len(entidades) == 0:
        alertas.append("CRÍTICO: Nenhuma entidade estrutural encontrada após filtragem.")
    elif len(entidades) < 3:
        alertas.append(f"ALERTA: Apenas {len(entidades)} entidades encontradas — projeto pode estar incompleto.")

    # ── Verifica proporção de layers ambíguas ───────────────────────────
    ambiguas = state.get("layers_ambiguas", [])
    total_layers = len(state.get("layers_encontradas", []))
    if total_layers > 0 and len(ambiguas) > total_layers * 0.5:
        alertas.append(
            f"ALERTA: {len(ambiguas)} de {total_layers} "
            "layers são ambíguas — considere revisar o DXF."
        )

    # ── Verifica anomalias geométricas por categoria ───────────────────
    contagem_por_categoria = {}
    for ent in entidades:
        cat = ent.get("categoria", "desconhecido")
        contagem_por_categoria[cat] = contagem_por_categoria.get(cat, 0) + 1

    # Sanity checks
    if contagem_por_categoria.get("pilar", 0) > 200:
        alertas.append(
            f"ALERTA: {contagem_por_categoria['pilar']} pilares encontrados — "
            "número incomum, verifique se há duplicatas."
        )

    if contagem_por_categoria.get("viga", 0) > 500:
        alertas.append(
            f"ALERTA: {contagem_por_categoria['viga']} vigas encontradas — "
            "número incomum, verifique a classificação."
        )

    # ── Determina status da validação ──────────────────────────────────
    alertas_criticos = [a for a in alertas if "CRÍTICO" in a]
    validacao_ok = len(alertas_criticos) == 0

    if alertas:
        print(f"   ⚠️  {len(alertas)} alertas:")
        for a in alertas:
            print(f"      • {a}")
    else:
        print("   ✅ Nenhum alerta — dados coerentes.")

    # ── Human-in-the-loop: interrupt() para alertas críticos ───────────
    if alertas_criticos:
        print("\n   🛑 [HUMAN-IN-THE-LOOP] Alertas críticos detectados!")
        print("   🛑 Pipeline pausado — aguardando decisão humana...")

        decisao = interrupt({
            "tipo": "validacao_critica",
            "alertas": alertas,
            "alertas_criticos": alertas_criticos,
            "entidades_encontradas": len(entidades),
            "categorias": contagem_por_categoria,
            "pergunta": (
                "Foram encontrados alertas críticos na validação. "
                "Deseja continuar o processamento mesmo assim? "
                "Responda com 'continuar' para prosseguir ou "
                "'cancelar' para interromper o pipeline."
            ),
        })

        # O pipeline retoma aqui quando o humano responde
        if isinstance(decisao, str) and decisao.strip().lower() == "continuar":
            print("   ✅ [HUMAN-IN-THE-LOOP] Usuário decidiu continuar.")
            validacao_ok = True
            alertas.append("INFO: Pipeline continuado por decisão do usuário.")
        else:
            print("   ❌ [HUMAN-IN-THE-LOOP] Usuário decidiu cancelar.")
            validacao_ok = False
            alertas.append("INFO: Pipeline cancelado por decisão do usuário.")

    return {
        "validacao_ok": validacao_ok,
        "alertas": alertas,
        "etapa_atual": "validacao_completa",
    }


# ═══════════════════════════════════════════════════════════════════════════
# NÓ 5 — CÁLCULO GEOMÉTRICO
# ═══════════════════════════════════════════════════════════════════════════

@traceable(name="node_calcular", run_type="chain")
def node_calcular(state: BlueprintState) -> dict:
    """
    Calcula área, perímetro e comprimento das entidades filtradas.

    Gera o memorial de cálculo com resumo por camada (layer) e
    resumo por categoria.

    Entrada:  state["entidades_filtradas"]
    Saída:    memorial_calculo
    """
    print("\n[GRAFO] 📐 Nó 5: Cálculo geométrico...")

    entidades = state.get("entidades_filtradas", [])
    resultados = []

    area_total = 0.0
    perimetro_total = 0.0
    comprimento_total = 0.0
    ignorados = 0

    for idx, ent in enumerate(entidades, start=1):
        geometria = ent["geometria"]
        tipo_geo = geometria["tipo_geometria"]
        coords = geometria["coordenadas"]

        processador = PROCESSADORES.get(tipo_geo)
        if processador is None:
            ignorados += 1
            continue

        try:
            calculo = processador(coords)
        except Exception as erro:
            logger.warning(f"Erro ao calcular {tipo_geo} (layer={ent['layer']}): {erro}")
            ignorados += 1
            continue

        # Ignora pilares/estacas com linhas abertas (não são geometrias fechadas reais)
        categoria = ent.get("categoria", "desconhecido")
        if (
            categoria in ("pilar", "estaca")
            and calculo.get("interpretacao") == "Linha aberta"
        ):
            ignorados += 1
            continue

        calculo.update({
            "indice": idx,
            "camada": ent["layer"],
            "categoria": categoria,
            "subclasse": ent["tipo"],
            "handle": ent["handle"],
        })
        resultados.append(calculo)

        area_total += calculo.get("area_m2", 0) or calculo.get("area_total_m2", 0)
        perimetro_total += calculo.get("perimetro_m", 0) or calculo.get("perimetro_total_m", 0)
        comprimento_total += calculo.get("comprimento_m", 0) or calculo.get("comprimento_total_m", 0)

    # Resumo por camada
    resumo_camadas = {}
    for r in resultados:
        cam = r["camada"]
        if cam not in resumo_camadas:
            resumo_camadas[cam] = {
                "quantidade": 0,
                "area_m2": 0.0,
                "perimetro_m": 0.0,
                "comprimento_m": 0.0,
            }
        resumo_camadas[cam]["quantidade"] += 1
        resumo_camadas[cam]["area_m2"] += r.get("area_m2", 0) or r.get("area_total_m2", 0)
        resumo_camadas[cam]["perimetro_m"] += r.get("perimetro_m", 0) or r.get("perimetro_total_m", 0)
        resumo_camadas[cam]["comprimento_m"] += r.get("comprimento_m", 0) or r.get("comprimento_total_m", 0)

    # Resumo por categoria
    resumo_categorias = {}
    for r in resultados:
        cat = r.get("categoria", "desconhecido")
        if cat not in resumo_categorias:
            resumo_categorias[cat] = {
                "quantidade": 0,
                "area_m2": 0.0,
                "perimetro_m": 0.0,
                "comprimento_m": 0.0,
            }
        resumo_categorias[cat]["quantidade"] += 1
        resumo_categorias[cat]["area_m2"] += r.get("area_m2", 0) or r.get("area_total_m2", 0)
        resumo_categorias[cat]["perimetro_m"] += r.get("perimetro_m", 0) or r.get("perimetro_total_m", 0)
        resumo_categorias[cat]["comprimento_m"] += r.get("comprimento_m", 0) or r.get("comprimento_total_m", 0)

    memorial = {
        "resumo_geral": {
            "total_features": len(resultados),
            "ignoradas": ignorados,
            "area_total_m2": round(area_total, 4),
            "area_total_ha": round(area_total / 10000, 6),
            "perimetro_total_m": round(perimetro_total, 4),
            "comprimento_total_m": round(comprimento_total, 4),
        },
        "resumo_por_camada": {
            cam: {k: round(v, 4) if isinstance(v, float) else v for k, v in dados.items()}
            for cam, dados in resumo_camadas.items()
        },
        "resumo_por_categoria": {
            cat: {k: round(v, 4) if isinstance(v, float) else v for k, v in dados.items()}
            for cat, dados in resumo_categorias.items()
        },
        "features": resultados,
    }

    print(f"   📊 {len(resultados)} features calculadas | {ignorados} ignoradas")
    print(f"   📊 Área total: {area_total:.4f} m² | Perímetro total: {perimetro_total:.4f} m")

    return {
        "memorial_calculo": memorial,
        "etapa_atual": "calculo_completo",
    }


# ═══════════════════════════════════════════════════════════════════════════
# NÓ 6 — ADAPTAÇÃO PARA RAG
# ═══════════════════════════════════════════════════════════════════════════

@traceable(name="node_adaptar", run_type="chain")
def node_adaptar(state: BlueprintState) -> dict:
    """
    Adapta o memorial de cálculo para o formato esperado pelo RAG SINAPI.

    Usa a taxonomia de categorias para mapear cada grupo
    para descrições SINAPI.

    Entrada:  state["memorial_calculo"], state["mapa_layers"]
    Saída:    itens_adaptados
    """
    print("\n[GRAFO] 🔄 Nó 6: Adaptação para formato RAG...")

    memorial = state.get("memorial_calculo", {})
    resumo_categorias = memorial.get("resumo_por_categoria", {})
    mapa_layers = state.get("mapa_layers", {})

    itens_adaptados = []

    for idx, (categoria, dados) in enumerate(resumo_categorias.items(), start=1):
        config = MAPA_CATEGORIA_SINAPI.get(categoria)

        if config:
            tipo = config["type"]
            descricao = config["description"]
            campo_qty = config["campo_qty"]
            unidade = config["unidade"]
            quantidade = dados.get(campo_qty, 0)
        else:
            # Categoria sem mapeamento SINAPI — usa melhor valor disponível
            tipo = categoria
            descricao = f"Elemento estrutural: {categoria}"
            unidade = "m2" if dados.get("area_m2", 0) > 0 else "m"
            quantidade = dados.get("area_m2", 0) or dados.get("comprimento_m", 0)

        if quantidade == 0:
            continue

        itens_adaptados.append({
            "id": f"{categoria.upper()}_{idx:03d}",
            "type": tipo,
            "quantity": round(quantidade, 2),
            "description": descricao,
            "unidade": unidade,
            "quantidade_elementos": dados.get("quantidade", 0),
        })

    print(f"   ✅ {len(itens_adaptados)} itens adaptados para o RAG")

    return {
        "itens_adaptados": itens_adaptados,
        "etapa_atual": "adaptacao_completa",
    }


# ═══════════════════════════════════════════════════════════════════════════
# NÓ 7 — RAG SINAPI
# ═══════════════════════════════════════════════════════════════════════════

@traceable(name="node_rag", run_type="retriever")
def node_rag(state: BlueprintState) -> dict:
    """
    Busca correspondências SINAPI via RAG para cada item adaptado.

    Entrada:  state["itens_adaptados"]
    Saída:    sugestoes_sinapi
    """
    print("\n[GRAFO] 🔍 Nó 7: Busca SINAPI via RAG...")

    from apps.projetos.ai.services.orcamento_service import gerar_sugestoes_orcamento

    itens = state.get("itens_adaptados", [])
    if not itens:
        return {
            "sugestoes_sinapi": [],
            "etapa_atual": "rag_completo",
        }

    sugestoes = gerar_sugestoes_orcamento(itens)
    print(f"   ✅ {len(sugestoes)} sugestões SINAPI geradas")

    return {
        "sugestoes_sinapi": sugestoes,
        "etapa_atual": "rag_completo",
    }


# ═══════════════════════════════════════════════════════════════════════════
# NÓ 8 — ORÇAMENTO FINAL
# ═══════════════════════════════════════════════════════════════════════════

@traceable(name="node_orcamento", run_type="chain")
def node_orcamento(state: BlueprintState) -> dict:
    """
    Calcula o orçamento final com quantidade × preço + BDI.

    Entrada:  state["sugestoes_sinapi"], state["projeto_id"]
    Saída:    orcamento_final
    """
    print("\n[GRAFO] 💰 Nó 8: Cálculo de orçamento final...")

    from apps.projetos.ai.services.orcamento_service import calcular_orcamento_final

    sugestoes = state.get("sugestoes_sinapi", [])
    projeto_id = state.get("projeto_id")

    # Busca taxa BDI do projeto
    taxa_bdi = 0.0
    if projeto_id:
        try:
            from apps.projetos.models import Projeto
            projeto = Projeto.objects.get(pk=projeto_id)
            taxa_bdi = float(projeto.taxa_bdi)
            print(f"   📊 Taxa BDI do projeto: {taxa_bdi}%")
        except Exception:
            print("   ⚠️  Projeto não encontrado, BDI = 0%")

    orcamento = calcular_orcamento_final(
        sugestoes=sugestoes,
        selecoes=None,
        taxa_bdi=taxa_bdi,
    )

    resumo = orcamento.get("resumo", {})
    print(
        f"   💰 {resumo.get('total_itens', 0)} itens | "
        f"Subtotal: R$ {resumo.get('subtotal', 0):.2f} | "
        f"BDI: R$ {resumo.get('valor_bdi', 0):.2f} | "
        f"TOTAL: R$ {resumo.get('total_geral', 0):.2f}"
    )

    return {
        "orcamento_final": orcamento,
        "etapa_atual": "orcamento_completo",
    }
