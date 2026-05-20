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
# NÓ 2 — EXTRAÇÃO ESTRUTURADA MANUAL (ezdxf)
# ═══════════════════════════════════════════════════════════════════════════════

@traceable(name="node_extraction_manual", run_type="chain")
def node_extraction_manual(state: DescritivoState) -> dict:
    """
    Executa a extração determinística do DXF usando a biblioteca ezdxf.

    Reutiliza o módulo dxf_core.extrair_dxf() existente para varrer
    camadas, blocos, linhas e textos, organizando por ambiente.

    Entrada:  state["caminho_dxf"]
    Saída:    extracao_bruta, ambientes, textos_legenda, resumo_por_camada, estatisticas
    """
    print("\n[GRAFO DESCRITIVO] 🔧 Nó 2: Extração Estruturada Manual (ezdxf)...")

    # Verificar se houve erro no nó anterior
    if state.get("erro"):
        print(f"   ⚠️  Pulando extração — erro anterior: {state['erro']}")
        return {"etapa_atual": "extracao_pulada"}

    caminho_dxf = state["caminho_dxf"]

    # ── Executar extração via dxf_core ───────────────────────────────────
    try:
        from apps.projetos.ai.extracaocalculo.dxf_core import extrair_dxf
        memorial_obj = extrair_dxf(caminho_dxf)
    except Exception as e:
        msg = f"Falha na extração DXF: {e}"
        logger.error(msg)
        print(f"   ❌ {msg}")
        return {
            "erro": msg,
            "etapa_atual": "erro_extracao",
        }

    # ── Converter dataclass para dict e sanitizar tipos do Numpy ────────
    def _sanitize_types(obj):
        if isinstance(obj, dict):
            return {k: _sanitize_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_sanitize_types(v) for v in obj]
        elif isinstance(obj, tuple):
            return tuple(_sanitize_types(v) for v in obj)
        # Converte qualquer tipo numérico do Numpy para Python nativo
        elif hasattr(obj, "item") and callable(obj.item):
            return obj.item()
        return obj

    memorial_dict = _sanitize_types(asdict(memorial_obj))

    # ── Organizar ambientes ──────────────────────────────────────────────
    ambientes = memorial_dict.get("ambientes", [])
    textos_legenda = memorial_dict.get("textos_legenda", [])

    # ── Montar resumo por camada ─────────────────────────────────────────
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

    # ── Estatísticas gerais ──────────────────────────────────────────────
    estatisticas = {
        "total_entidades": memorial_obj.total_entidades,
        "total_ignoradas": memorial_obj.total_ignoradas,
        "total_camadas": len(resumo_camadas),
        "total_ambientes": len(ambientes),
    }

    print(f"   ✅ Extração concluída:")
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

    # ── Preparar dados para o prompt ─────────────────────────────────────
    metadados_str = json.dumps(state.get("metadados_obra", {}), ensure_ascii=False, indent=2)
    ambientes_str = json.dumps(state.get("ambientes", []), ensure_ascii=False, indent=2)
    textos_str = json.dumps(state.get("textos_legenda", []), ensure_ascii=False, indent=2)
    resumo_str = json.dumps(state.get("resumo_por_camada", {}), ensure_ascii=False, indent=2)
    estatisticas_str = json.dumps(state.get("estatisticas", {}), ensure_ascii=False, indent=2)

    # ── Montar prompt formatado ──────────────────────────────────────────
    user_prompt = USER_PROMPT_MEMORIAL_DESCRITIVO.format(
        metadados_obra=metadados_str,
        ambientes=ambientes_str,
        textos_legenda=textos_str,
        resumo_por_camada=resumo_str,
        estatisticas=estatisticas_str,
    )

    print(f"   📝 Prompt montado ({len(user_prompt)} caracteres)")
    print(f"   🔄 Invocando LLM...")

    # ── Invocar a LLM ───────────────────────────────────────────────────
    try:
        llm = get_chat_llm()
        mensagens = [
            SystemMessage(content=SYSTEM_PROMPT_AUDITOR),
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
