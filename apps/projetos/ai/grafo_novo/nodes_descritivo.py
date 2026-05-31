"""
nodes_descritivo.py
====================
Implementação dos 4 nós do grafo LangGraph para o Memorial Descritivo.

Cada função:
  - Recebe o DescritivoState completo
  - Executa sua lógica
  - Retorna um dict parcial com as chaves modificadas

Nós:
  1. node_upload_cadastro    — Validação do DXF + carregamento de metadados
  2. node_extraction_manual  — Extração determinística com ezdxf (dxf_core)
  3. node_llm_analyst        — Agente LLM auditor para gerar o Memorial Descritivo
  4. node_storage_export     — Persistência no DB + geração de PDF

Observabilidade:
  - Todos os nós decorados com @traceable (LangSmith)
"""

import json
import logging
import os
import sys

from dataclasses import asdict
from langsmith import traceable

# Forçar UTF-8 no Windows para evitar erros com emojis
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from apps.projetos.ai.grafo_novo.state_descritivo import DescritivoState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# NÓ 1 — INPUT & CADASTRO
# ═══════════════════════════════════════════════════════════════════════════════

@traceable(name="node_upload_cadastro", run_type="chain")
def node_upload_cadastro(state: DescritivoState) -> dict:
    """
    Recebe e valida o upload do arquivo DXF e os metadados de cadastro da obra.

    Responsabilidades:
      - Verificar se o arquivo DXF existe no caminho informado
      - Carregar metadados do Projeto Django (se projeto_id fornecido)
      - Consolidar metadados_obra com dados do banco

    Entrada:  state["caminho_dxf"], state["projeto_id"], state["metadados_obra"]
    Saída:    metadados_obra (enriquecido), etapa_atual
    """
    print("\n[GRAFO DESCRITIVO] 📋 Nó 1: Input & Cadastro...")

    caminho_dxf = state.get("caminho_dxf", "")
    projeto_id = state.get("projeto_id")
    metadados = state.get("metadados_obra", {})

    # ── Validar existência do arquivo DXF ────────────────────────────────
    if not caminho_dxf or not os.path.isfile(caminho_dxf):
        msg = f"Arquivo DXF não encontrado: {caminho_dxf}"
        print(f"   ❌ {msg}")
        return {
            "erro": msg,
            "etapa_atual": "erro_upload",
        }

    if not caminho_dxf.lower().endswith(".dxf"):
        msg = f"Arquivo não é .DXF: {caminho_dxf}"
        print(f"   ❌ {msg}")
        return {
            "erro": msg,
            "etapa_atual": "erro_upload",
        }

    print(f"   ✅ Arquivo DXF validado: {os.path.basename(caminho_dxf)}")
    print(f"      Tamanho: {os.path.getsize(caminho_dxf) / 1024:.1f} KB")

    # ── Carregar metadados do banco (se disponível) ──────────────────────
    if projeto_id:
        try:
            from apps.projetos.models import Projeto
            projeto = Projeto.objects.get(pk=projeto_id)

            # Enriquecer metadados com dados do projeto Django
            metadados.setdefault("nome", projeto.nome_obra)
            metadados.setdefault(
                "localizacao",
                f"{projeto.cidade_obra}, {projeto.estado_obra}",
            )
            if projeto.desc_obra:
                metadados.setdefault("descricao", projeto.desc_obra)

            print(f"   📊 Projeto carregado: {projeto.nome_obra}")
        except Exception as e:
            logger.warning(f"Projeto {projeto_id} não encontrado: {e}")
            print(f"   ⚠️  Projeto {projeto_id} não encontrado no banco")

    # ── Garantir campos obrigatórios nos metadados ───────────────────────
    metadados.setdefault("nome", "Obra não identificada")
    metadados.setdefault("localizacao", "Não informada")
    metadados.setdefault("tipo_construcao", "Não informado")
    metadados.setdefault("padrao_acabamento", "Não informado")

    print(f"   📊 Metadados: {json.dumps(metadados, ensure_ascii=False)}")

    return {
        "metadados_obra": metadados,
        "etapa_atual": "cadastro_completo",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NÓ 2 — EXTRAÇÃO ESTRUTURADA MANUAL (ezdxf + CAD Engine opcional)
# ═══════════════════════════════════════════════════════════════════════════════

@traceable(name="node_extraction_manual", run_type="chain")
def node_extraction_manual(state: DescritivoState) -> dict:
    """
    Executa a extração determinística do DXF.

    Se use_cad_engine=True, utiliza o novo CAD engine (core/cad) com:
      - Parser robusto (blocos, XREF, OCS, unidades, bulge-to-arc)
      - Healing (snap de vertices + remocao de duplicatas)
      - Polygonizacao via shapely (segmentos -> poligonos)
      - Validacao e reparo de poligonos
      - Metricas com adjacencia entre ambientes
      - Classificador semantico texto-poligono
      - Grafo de topologia networkx
      - Parametros adaptativos (auto-escala)

    Caso contrario (default), usa o modulo dxf_core.extrair_dxf() existente.

    Entrada:  state["caminho_dxf"], state["use_cad_engine"]
    Saida:    extracao_bruta, ambientes, textos_legenda, resumo_por_camada,
              estatisticas, e (se cad engine) cad_* enriquecidos
    """
    print("\n[GRAFO DESCRITIVO] 🔧 Nó 2: Extração Estruturada Manual (ezdxf)...")

    if state.get("erro"):
        print(f"   ⚠️  Pulando extracao — erro anterior: {state['erro']}")
        return {"etapa_atual": "extracao_pulada"}

    caminho_dxf = state["caminho_dxf"]
    use_cad = state.get("use_cad_engine", False)

    if use_cad:
        return _extrair_com_cad_engine(caminho_dxf)
    else:
        return _extrair_com_dxf_core(caminho_dxf)


def _extrair_com_cad_engine(caminho_dxf: str) -> dict:
    """
    Extracao combinada: CAD engine (polygonizacao) + dxf_core (elementos estruturais).

    Executa AMBOS os engines e mescla os resultados:
      - CAD engine: parse -> flatten -> heal -> polygonize -> validate -> metrics -> classify -> geojson
      - dxf_core:  extracao classica por layer (paredes, pilares, vigas, volumes)

    O LLM recebe dados estruturais completos + geometria enriquecida.
    """
    print("   🚀 Usando CAD Engine + dxf_core (combinado)...")

    # ── 1. Executar CAD engine ────────────────────────────────────────
    try:
        from apps.projetos.ai.cad.engine import process_dxf
        cad_result = process_dxf(caminho_dxf)
    except Exception as e:
        msg = f"Falha no CAD engine: {e}"
        logger.error(msg)
        print(f"   ❌ {msg}")
        return {"erro": msg, "etapa_atual": "erro_extracao"}

    cad_ok = cad_result.success

    # ── 2. Executar dxf_core (elementos estruturais) ──────────────────
    estrutural_ok = False
    memorial_dict = {}
    resumo_estrutural = {}
    estatisticas_estruturais = {}
    ambientes_dxf = []
    textos_dxf = []
    try:
        from apps.projetos.ai.extracaocalculo.dxf_core import extrair_dxf
        from dataclasses import asdict

        memorial_obj = extrair_dxf(caminho_dxf)

        def _sanitize(obj):
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_sanitize(v) for v in obj]
            elif isinstance(obj, tuple):
                return tuple(_sanitize(v) for v in obj)
            elif hasattr(obj, "item") and callable(obj.item):
                return obj.item()
            return obj

        memorial_dict = _sanitize(asdict(memorial_obj))
        ambientes_dxf = memorial_dict.get("ambientes", [])
        textos_dxf = memorial_dict.get("textos_legenda", [])

        for chave, dados in memorial_dict.get("resumo_por_camada", {}).items():
            resumo_estrutural[chave] = {
                "categoria": dados.get("categoria", "desconhecido"),
                "quantidade": dados.get("quantidade", 0),
                "area_total_m2": dados.get("area_total_m2", 0.0),
                "perimetro_total_m": dados.get("perimetro_total_m", 0.0),
                "comprimento_total_m": dados.get("comprimento_total_m", 0.0),
                "volume_m3": dados.get("volume_m3", 0.0),
                "area_liquida_m2": dados.get("area_liquida_m2", 0.0),
            }

        estatisticas_estruturais = {
            "total_entidades": memorial_obj.total_entidades,
            "total_ignoradas": memorial_obj.total_ignoradas,
            "total_camadas": len(resumo_estrutural),
            "total_ambientes_dxf": len(ambientes_dxf),
        }
        estrutural_ok = True
        print(f"   ✅ dxf_core concluido: {estatisticas_estruturais['total_entidades']} entidades, "
              f"{estatisticas_estruturais['total_camadas']} camadas")
    except Exception as e:
        logger.warning(f"dxf_core falhou (usando so CAD engine): {e}")
        print(f"   ⚠️  dxf_core falhou: {e}")

    # ── 3. Mesclar resultados ─────────────────────────────────────────
    #
    # HIERARQUIA DE DADOS (prioridade decrescente):
    #   1. Texto anotado no DXF (MTEXT com área/perímetro/pé-direito)
    #      → fonte PRIMÁRIA para valores numéricos
    #   2. Polígonos do CAD engine
    #      → geometria, adjacência, layout (GeoJSON)
    #   3. dxf_core (extração por layer)
    #      → dados estruturais (paredes, pilares, vigas, volumes)

    # Construir lookup de ambientes MTEXT por nome para cruzamento
    ambientes_mtext_by_name = {}
    for amb in ambientes_dxf:
        nome = amb.get("nome", "").strip().upper()
        if nome:
            ambientes_mtext_by_name[nome] = amb

    # Ambientes: priorizar dados textuais, enriquecer com geometria do CAD
    ambientes_final = []
    fonte_area = "nenhuma"

    if ambientes_dxf:
        # Caso 1: MTEXT contém ambientes com área → fonte primária
        fonte_area = "mtext"
        for amb in ambientes_dxf:
            amb_out = {
                "nome": amb.get("nome", "?"),
                "area_m2": amb.get("area_m2", 0.0),
                "perimetro_m": amb.get("perimetro_m", 0.0),
                "pe_direito_m": amb.get("pe_direito_m", 0.0),
                "fonte_area": "texto_dxf",
            }
            ambientes_final.append(amb_out)

    if cad_ok and cad_result.rooms:
        if not ambientes_final:
            # Caso 2: Sem MTEXT → usar CAD engine como fonte
            fonte_area = "cad_engine"
            for room in cad_result.rooms:
                idx = room["index"]
                if cad_result.used_text_fallback and room.get("area_m2") is not None:
                    area_m2 = room["area_m2"]
                    perimetro_m = 0.0
                    fonte = "texto_fallback"
                elif cad_result.metrics and idx < len(cad_result.metrics.rooms):
                    rm = cad_result.metrics.rooms[idx]
                    area_m2 = rm.area_m2 if rm and rm.is_valid else 0.0
                    perimetro_m = rm.perimeter_m if rm and rm.is_valid else 0.0
                    fonte = "poligono_calculado"
                else:
                    area_m2 = 0.0
                    perimetro_m = 0.0
                    fonte = "indisponivel"
                ambientes_final.append({
                    "nome": room.get("nome_sugerido", f"Ambiente {idx + 1}"),
                    "area_m2": area_m2,
                    "perimetro_m": perimetro_m,
                    "pe_direito_m": 0.0,
                    "fonte_area": fonte,
                })
        else:
            # Caso 3: Ambos disponíveis → cruzar nomes para enriquecer MTEXT
            # com dados geométricos do CAD (centroid, adjacência), mas manter
            # áreas do MTEXT como verdade
            for room in cad_result.rooms:
                nome_cad = room.get("nome_sugerido", "").strip().upper()
                if nome_cad in ambientes_mtext_by_name:
                    # Já existe via MTEXT — não duplicar
                    continue
                # Ambiente detectado pelo CAD mas não no MTEXT — adicionar
                idx = room["index"]
                if cad_result.metrics and idx < len(cad_result.metrics.rooms):
                    rm = cad_result.metrics.rooms[idx]
                    area_m2 = rm.area_m2 if rm and rm.is_valid else 0.0
                    perimetro_m = rm.perimeter_m if rm and rm.is_valid else 0.0
                else:
                    area_m2 = 0.0
                    perimetro_m = 0.0
                ambientes_final.append({
                    "nome": room.get("nome_sugerido", f"Ambiente {idx + 1}"),
                    "area_m2": area_m2,
                    "perimetro_m": perimetro_m,
                    "pe_direito_m": 0.0,
                    "fonte_area": "poligono_cad_complementar",
                })

    # Textos: mescla sem duplicatas
    textos_set = set()
    textos_final = []
    if cad_ok:
        for t in cad_result.texts:
            chave = t.get("texto", "") + t.get("layer", "")
            if chave not in textos_set:
                textos_set.add(chave)
                textos_final.append(t)
    for t in textos_dxf:
        chave = t.get("texto", "") + t.get("layer", "")
        if chave not in textos_set:
            textos_set.add(chave)
            textos_final.append(t)

    # Resumo por camada: junta dados estruturais + ambientes do CAD
    resumo_camadas = dict(resumo_estrutural)
    if cad_ok and cad_result.metrics:
        for i, room_metric in enumerate(cad_result.metrics.rooms):
            if not room_metric.is_valid:
                continue
            nome = cad_result.rooms[i].get("nome_sugerido", f"Ambiente_{i}") if i < len(cad_result.rooms) else f"Ambiente_{i}"
            if nome not in resumo_camadas:
                resumo_camadas[nome] = {
                    "categoria": "ambiente",
                    "quantidade": 1,
                    "area_total_m2": room_metric.area_m2,
                    "perimetro_total_m": room_metric.perimeter_m,
                    "comprimento_total_m": 0.0,
                    "volume_m3": 0.0,
                    "area_liquida_m2": room_metric.area_m2,
                }

    # Área total: preferir soma do MTEXT se disponível
    if fonte_area == "mtext":
        total_area_mtext = sum(a.get("area_m2", 0) or 0 for a in ambientes_dxf)
        total_area = total_area_mtext if total_area_mtext > 0 else (
            cad_result.metrics.total_area if cad_ok and cad_result.metrics else 0.0
        )
    else:
        total_area = cad_result.metrics.total_area if cad_ok and cad_result.metrics else 0.0
    total_perim = cad_result.metrics.total_perimeter if cad_ok and cad_result.metrics else 0.0

    estatisticas = {
        **estatisticas_estruturais,
        "total_ambientes": len(ambientes_final),
        "total_area_m2": total_area,
        "total_perimetro_m": total_perim,
        "fonte_area_primaria": fonte_area,
        "segmentos_brutos": cad_result.stats.get("segmentos_brutos", 0) if cad_ok else 0,
        "segmentos_healed": cad_result.stats.get("segmentos_healed", 0) if cad_ok else 0,
        "poligonos": cad_result.stats.get("poligonos", 0) if cad_ok else 0,
        "dangles": cad_result.stats.get("dangles", 0) if cad_ok else 0,
        "invalid_rings": cad_result.stats.get("invalid_rings", 0) if cad_ok else 0,
    }

    cad_adjacency = cad_result.metrics.adjacency if cad_ok and cad_result.metrics else {}
    cad_topology_stats = {
        "vertices_grafo": cad_result.stats.get("vertices_grafo", -1) if cad_ok else -1,
        "arestas_grafo": cad_result.stats.get("arestas_grafo", -1) if cad_ok else -1,
    }

    print(f"\n   ✅ Extracao combinada concluida:")
    print(f"      Fonte area primaria: {fonte_area}")
    print(f"      Entidades: {estatisticas.get('total_entidades', 0)}")
    print(f"      Camadas:   {estatisticas.get('total_camadas', 0)}")
    print(f"      Ambientes: {estatisticas['total_ambientes']}")
    print(f"      Poligonos: {estatisticas['poligonos']}")
    print(f"      Area total: {total_area:.2f} m²")
    if cad_ok:
        print(f"      Segmentos: {estatisticas['segmentos_brutos']} -> {estatisticas['segmentos_healed']} (healed)")
        print(f"      Adjacencias: {len(cad_adjacency)}")

    return {
        "extracao_bruta": memorial_dict if memorial_dict else {
            "cad_stats": cad_result.stats if cad_ok else {},
            "estrutural_disponivel": estrutural_ok,
        },
        "ambientes": ambientes_final,
        "textos_legenda": textos_final,
        "resumo_por_camada": resumo_camadas,
        "estatisticas": estatisticas,
        "cad_engine_result": {
            "success": cad_ok,
            "stats": cad_result.stats if cad_ok else {},
            "error": cad_result.error if not cad_ok else None,
            "used_text_fallback": cad_result.used_text_fallback if cad_ok else False,
        },
        "cad_polygons_geojson": cad_result.geojson if cad_ok else None,
        "cad_rooms": cad_result.rooms if cad_ok else [],
        "cad_adjacency": cad_adjacency,
        "cad_topology_stats": cad_topology_stats,
        "cad_full_report": cad_result.full_report if cad_ok and cad_result.full_report else None,
        "etapa_atual": "extracao_completa",
    }


def _extrair_com_dxf_core(caminho_dxf: str) -> dict:
    """Extracao usando o modulo dxf_core existente."""
    try:
        from apps.projetos.ai.extracaocalculo.dxf_core import extrair_dxf
        memorial_obj = extrair_dxf(caminho_dxf)
    except Exception as e:
        msg = f"Falha na extracao DXF: {e}"
        logger.error(msg)
        print(f"   ❌ {msg}")
        return {"erro": msg, "etapa_atual": "erro_extracao"}

    def _sanitize_types(obj):
        if isinstance(obj, dict):
            return {k: _sanitize_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_sanitize_types(v) for v in obj]
        elif isinstance(obj, tuple):
            return tuple(_sanitize_types(v) for v in obj)
        elif hasattr(obj, "item") and callable(obj.item):
            return obj.item()
        return obj

    memorial_dict = _sanitize_types(asdict(memorial_obj))

    ambientes = memorial_dict.get("ambientes", [])
    textos_legenda = memorial_dict.get("textos_legenda", [])

    resumo_camadas = {}
    for chave, dados in memorial_dict.get("resumo_por_camada", {}).items():
        resumo_camadas[chave] = {
            "categoria": dados.get("categoria", "desconhecido"),
            "quantidade": dados.get("quantidade", 0),
            "area_total_m2": dados.get("area_total_m2", 0.0),
            "perimetro_total_m": dados.get("perimetro_total_m", 0.0),
            "comprimento_total_m": dados.get("comprimento_total_m", 0.0),
            "volume_m3": dados.get("volume_m3", 0.0),
            "area_liquida_m2": dados.get("area_liquida_m2", 0.0),
        }

    estatisticas = {
        "total_entidades": memorial_obj.total_entidades,
        "total_ignoradas": memorial_obj.total_ignoradas,
        "total_camadas": len(resumo_camadas),
        "total_ambientes": len(ambientes),
    }

    print(f"   ✅ Extracao dxf_core concluida:")
    print(f"      Entidades: {estatisticas['total_entidades']}")
    print(f"      Ignoradas: {estatisticas['total_ignoradas']}")
    print(f"      Camadas:   {estatisticas['total_camadas']}")
    print(f"      Ambientes: {estatisticas['total_ambientes']}")

    if ambientes:
        print(f"   🏠 Ambientes detectados:")
        for amb in ambientes:
            print(f"      • {amb.get('nome', '?')}: "
                  f"{amb.get('area_m2', 0):.2f}m² | "
                  f"P={amb.get('perimetro_m', 0):.2f}m | "
                  f"PD={amb.get('pe_direito_m', 0):.2f}m")

    retorno = {
        "extracao_bruta": memorial_dict,
        "ambientes": ambientes,
        "textos_legenda": textos_legenda,
        "resumo_por_camada": resumo_camadas,
        "estatisticas": estatisticas,
        "etapa_atual": "extracao_completa",
    }

    return _sanitize_types(retorno)


# ═══════════════════════════════════════════════════════════════════════════════
# NÓ 3 — AGENTE DE ANÁLISE E AUDITORIA COM LLM
# ═══════════════════════════════════════════════════════════════════════════════

@traceable(name="node_llm_analyst", run_type="chain")
def node_llm_analyst(state: DescritivoState) -> dict:
    """
    Agente de IA (LLM) atuando como engenheiro auditor.

    Recebe o JSON da extração bruta + metadados da obra e gera o
    Memorial Descritivo completo com análise de inconsistências.

    Entrada:  state["extracao_bruta"], state["metadados_obra"], state["ambientes"],
              state["textos_legenda"], state["resumo_por_camada"], state["estatisticas"]
    Saída:    memorial_descritivo, inconsistencias, confianca_analise
    """
    print("\n[GRAFO DESCRITIVO] 🤖 Nó 3: Agente LLM Auditor (Memorial Descritivo)...")

    # Verificar se houve erro nos nós anteriores
    if state.get("erro"):
        print(f"   ⚠️  Pulando análise LLM — erro anterior: {state['erro']}")
        return {"etapa_atual": "analise_pulada"}

    # ── Importar dependências da LLM ─────────────────────────────────────
    from langchain_core.messages import SystemMessage, HumanMessage
    from apps.projetos.ai.client import get_chat_llm
    from apps.projetos.ai.prompts_descritivo import (
        SYSTEM_PROMPT_AUDITOR,
        USER_PROMPT_MEMORIAL_DESCRITIVO,
    )
    from apps.projetos.ai.nbrs import inject_nbrs_into_prompt
    metadados_obra = state.get("metadados_obra", {})
    ambientes = state.get("ambientes", [])
    contexto_obra = f"{metadados_obra.get('tipo_construcao', '')} {metadados_obra.get('nome', '')} ambientes: {', '.join(a.get('nome', '') for a in ambientes)}"
    system_prompt = inject_nbrs_into_prompt(SYSTEM_PROMPT_AUDITOR, contexto_obra=contexto_obra, k=5)

    # ── Preparar dados para o prompt ─────────────────────────────────────
    descricao_obra = metadados_obra.get("descricao") or "Não informada"
    metadados_str = json.dumps(state.get("metadados_obra", {}), ensure_ascii=False, indent=2)
    ambientes_str = json.dumps(state.get("ambientes", []), ensure_ascii=False, indent=2)
    textos_str = json.dumps(state.get("textos_legenda", []), ensure_ascii=False, indent=2)
    resumo_str = json.dumps(state.get("resumo_por_camada", {}), ensure_ascii=False, indent=2)
    estatisticas_str = json.dumps(state.get("estatisticas", {}), ensure_ascii=False, indent=2)
    cad_geojson_str = json.dumps(state.get("cad_polygons_geojson", {}), ensure_ascii=False, indent=2)
    cad_adj_str = json.dumps(state.get("cad_adjacency", {}), ensure_ascii=False, indent=2)
    cad_topology_str = json.dumps(state.get("cad_topology_stats", {}), ensure_ascii=False, indent=2)

    full_report = state.get("cad_full_report", {})
    blocos = full_report.get("blocos_detalhados", [])
    blocos_por_tipo = full_report.get("blocos_por_tipo", {})
    blocos_str = json.dumps({"por_tipo": blocos_por_tipo, "detalhados": blocos}, ensure_ascii=False, indent=2)
    dimensoes_str = json.dumps(full_report.get("dimensoes", []), ensure_ascii=False, indent=2)
    camadas_str = json.dumps(full_report.get("camadas", {}), ensure_ascii=False, indent=2)
    textos_por_camada_str = json.dumps(full_report.get("textos_por_camada", {}), ensure_ascii=False, indent=2)
    full_report_compact = {
        "camadas": full_report.get("camadas", {}),
        "blocos_por_tipo": blocos_por_tipo,
        "total_blocos": full_report.get("total_blocos", 0),
        "total_dimensoes": full_report.get("total_dimensoes", 0),
        "total_textos": full_report.get("total_textos", 0),
        "textos_por_camada": full_report.get("textos_por_camada", {}),
        "total_entidades": full_report.get("total_entidades", 0),
        "unidade": full_report.get("unidade", ""),
    }
    full_report_str = json.dumps(full_report_compact, ensure_ascii=False, indent=2)

    used_text_fallback = state.get("cad_engine_result", {}).get("used_text_fallback", False)
    if used_text_fallback:
        fallback_msg = "✅ ATIVADO: áreas dos ambientes vieram dos textos TXT_ÁREA (fonte primária)"
    else:
        fallback_msg = "❌ DESATIVADO: áreas vieram do cálculo geométrico de polígonos"
    cad_used_text_fallback = fallback_msg

    # ── Montar prompt formatado ──────────────────────────────────────────
    user_prompt = USER_PROMPT_MEMORIAL_DESCRITIVO.format(
        metadados_obra=metadados_str,
        descricao_obra=descricao_obra,
        ambientes=ambientes_str,
        textos_legenda=textos_str,
        resumo_por_camada=resumo_str,
        estatisticas=estatisticas_str,
        cad_polygons_geojson=cad_geojson_str,
        cad_adjacency=cad_adj_str,
        cad_topology_stats=cad_topology_str,
        cad_blocos=blocos_str,
        cad_dimensoes=dimensoes_str,
        cad_full_report=full_report_str,
        cad_used_text_fallback=cad_used_text_fallback,
    )

    print(f"   📝 Prompt montado ({len(user_prompt)} caracteres)")
    print(f"   🔄 Invocando LLM...")

    # ── Invocar a LLM ───────────────────────────────────────────────────
    try:
        llm = get_chat_llm()
        mensagens = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        resposta = llm.invoke(mensagens)
        texto_resposta = resposta.content.strip()
    except Exception as e:
        msg = f"Falha na invocação da LLM: {e}"
        logger.error(msg)
        print(f"   ❌ {msg}")
        return {
            "erro": msg,
            "etapa_atual": "erro_llm",
        }

    # ── Fazer parse do JSON retornado ────────────────────────────────────
    try:
        # Tentar extrair JSON de blocos de código markdown se a LLM envolver
        texto_limpo = texto_resposta
        if "```json" in texto_limpo:
            texto_limpo = texto_limpo.split("```json", 1)[1]
            texto_limpo = texto_limpo.split("```", 1)[0]
        elif "```" in texto_limpo:
            texto_limpo = texto_limpo.split("```", 1)[1]
            texto_limpo = texto_limpo.split("```", 1)[0]

        memorial_descritivo = json.loads(texto_limpo.strip())
    except json.JSONDecodeError as e:
        logger.warning(f"LLM retornou JSON inválido: {e}")
        print(f"   ⚠️  JSON inválido — salvando resposta bruta como texto")

        # Fallback: salvar resposta bruta em formato estruturado mínimo
        memorial_descritivo = {
            "dados_gerais": state.get("metadados_obra", {}),
            "resposta_bruta_llm": texto_resposta,
            "parse_error": str(e),
            "ambientes": state.get("ambientes", []),
            "elementos_estruturais": {},
            "instalacoes": {},
            "observacoes_tecnicas": ["Falha no parse do JSON da LLM — resposta bruta preservada."],
            "inconsistencias_detectadas": [],
            "confianca_analise": "baixa",
        }

    # ── Extrair inconsistências e confiança ──────────────────────────────
    inconsistencias = memorial_descritivo.get("inconsistencias_detectadas", [])
    confianca = memorial_descritivo.get("confianca_analise", "media")

    print(f"   ✅ Memorial Descritivo gerado pela LLM")
    print(f"      Confiança: {confianca}")
    print(f"      Inconsistências: {len(inconsistencias)}")
    if inconsistencias:
        for inc in inconsistencias[:5]:  # Limitar impressão
            print(f"      ⚠️  {inc}")
        if len(inconsistencias) > 5:
            print(f"      ... e mais {len(inconsistencias) - 5}")

    return {
        "memorial_descritivo": memorial_descritivo,
        "inconsistencias": inconsistencias,
        "confianca_analise": confianca,
        "etapa_atual": "analise_completa",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NÓ 4 — PERSISTÊNCIA & EXPORTAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

@traceable(name="node_storage_export", run_type="chain")
def node_storage_export(state: DescritivoState) -> dict:
    """
    Salva o Memorial Descritivo no banco de dados e gera o PDF.

    Responsabilidades:
      - Criar/atualizar registro Memorial no banco (campo memorial_descritivo)
      - Gerar PDF formatado via pdf_generator
      - Retornar confirmação e caminho do PDF

    Entrada:  state["memorial_descritivo"], state["projeto_id"], state["metadados_obra"]
    Saída:    memorial_db_id, pdf_path, exportacao_ok
    """
    print("\n[GRAFO DESCRITIVO] 💾 Nó 4: Persistência & Exportação...")

    # Verificar se houve erro nos nós anteriores
    if state.get("erro"):
        print(f"   ⚠️  Pulando exportação — erro anterior: {state['erro']}")
        return {
            "exportacao_ok": False,
            "etapa_atual": "exportacao_pulada",
        }

    memorial_descritivo = state.get("memorial_descritivo", {})
    projeto_id = state.get("projeto_id")
    metadados = state.get("metadados_obra", {})
    memorial_db_id = None
    pdf_path = None

    # ── Persistir no banco de dados ──────────────────────────────────────
    if projeto_id:
        try:
            from apps.projetos.models import Projeto, Memorial

            projeto = Projeto.objects.get(pk=projeto_id)

            memorial_obj = Memorial.objects.create(
                projeto=projeto,
                memorial_descritivo=memorial_descritivo,
            )
            memorial_db_id = memorial_obj.pk

            print(f"   ✅ Memorial salvo no banco: ID={memorial_db_id}")
        except Exception as e:
            logger.error(f"Erro ao salvar memorial no banco: {e}")
            print(f"   ❌ Erro ao salvar no banco: {e}")
    else:
        print(f"   ⚠️  Sem projeto_id — memorial não salvo no banco")

    # ── Gerar PDF ────────────────────────────────────────────────────────
    try:
        from apps.projetos.ai.services.pdf_generator import gerar_pdf_memorial_descritivo

        # Definir caminho de saída do PDF
        from django.conf import settings
        media_root = getattr(settings, "MEDIA_ROOT", ".")
        pdf_dir = os.path.join(media_root, "memoriais", "descritivo")
        os.makedirs(pdf_dir, exist_ok=True)

        nome_arquivo = metadados.get("nome", "obra").replace(" ", "_").lower()
        if memorial_db_id:
            pdf_filename = f"memorial_descritivo_{memorial_db_id}_{nome_arquivo}.pdf"
        else:
            import uuid
            pdf_filename = f"memorial_descritivo_{uuid.uuid4().hex[:8]}_{nome_arquivo}.pdf"

        pdf_path = os.path.join(pdf_dir, pdf_filename)

        gerar_pdf_memorial_descritivo(
            memorial_dict=memorial_descritivo,
            metadados=metadados,
            output_path=pdf_path,
        )
        print(f"   ✅ PDF gerado: {pdf_path}")
    except ImportError:
        logger.warning("reportlab não instalado — PDF não gerado")
        print("   ⚠️  reportlab não instalado — pulando geração de PDF")
        print("   💡 Instale com: pip install reportlab")
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        print(f"   ❌ Erro ao gerar PDF: {e}")

    exportacao_ok = memorial_db_id is not None or pdf_path is not None

    print(f"\n   📊 Resumo da exportação:")
    print(f"      Banco de dados: {'✅' if memorial_db_id else '❌'}")
    print(f"      PDF:            {'✅' if pdf_path else '❌'}")

    return {
        "memorial_db_id": memorial_db_id,
        "pdf_path": pdf_path,
        "exportacao_ok": exportacao_ok,
        "etapa_atual": "exportacao_completa",
    }
