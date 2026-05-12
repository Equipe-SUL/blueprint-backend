"""
layer_classifier.py
====================
Classificação de layers DXF usando LLM (Ollama/Gemma).

Para layers que as regras determinísticas (taxonomy.py) não conseguem
classificar, a LLM analisa o nome da layer e infere a categoria.

Fluxo:
  1. Tenta classificar todas as layers por regras determinísticas
  2. Envia apenas as layers "desconhecidas" para a LLM
  3. Retorna um mapa completo: layer → categoria
"""

import json
import logging
from typing import Dict, List

from apps.projetos.ai.client import get_chat_llm
from apps.projetos.ai.classification.taxonomy import (
    classificar_layer_por_regra,
    CATEGORIAS_VALIDAS,
)

logger = logging.getLogger(__name__)


# ── Prompt para classificação de layers via LLM ─────────────────────────────

PROMPT_CLASSIFICAR_LAYERS = """Você é um engenheiro civil especialista em projetos estruturais.
Analise os nomes de layers (camadas) de um arquivo DXF e classifique cada uma.

LAYERS PARA CLASSIFICAR:
{layers}

CATEGORIAS VÁLIDAS:
- pilar     → Pilares de concreto armado
- viga      → Vigas de concreto armado
- laje      → Lajes de concreto armado
- estaca    → Estacas de fundação
- fundacao  → Fundações (sapatas, blocos, radier)
- parede    → Paredes de alvenaria e vedação
- tubulacao → Tubulação hidráulica/sanitária
- eletrica  → Instalações elétricas
- anotacao  → Cotas, textos, legendas, carimbo
- desconhecido → Não conseguiu identificar

REGRAS:
1. Analise o nome completo da layer e infira a categoria mais provável.
2. Layers com nomes genéricos como "0" devem ser "desconhecido".
3. Considere prefixos comuns: S-, E-, EST-, STR- (estrutura), H- (hidráulica).
4. Considere sufixos comuns: -PROJ, -EXIST, -01, -02 (numeração).

RESPONDA APENAS com um JSON válido no formato:
{{"nome_layer_1": "categoria", "nome_layer_2": "categoria"}}

Sem texto extra, sem blocos de código markdown. Apenas o JSON puro.
"""


def classificar_layers(
    layers: List[str],
    usar_llm: bool = True,
) -> Dict[str, str]:
    """
    Classifica todas as layers em categorias estruturais.

    Etapa 1: Classificação determinística (regras hardcoded)
    Etapa 2: Classificação por LLM (apenas layers não resolvidas)

    Parâmetros:
        layers   : lista de nomes de layers encontradas no DXF
        usar_llm : se True, envia layers ambíguas para a LLM

    Retorna:
        dict mapeando cada layer para sua categoria
    """
    mapa_final = {}
    layers_ambiguas = []

    # ── Etapa 1: Regras determinísticas ──────────────────────────────────
    for layer in layers:
        categoria = classificar_layer_por_regra(layer)
        mapa_final[layer] = categoria

        if categoria == "desconhecido":
            layers_ambiguas.append(layer)

    print(f"   🏷️  [CLASSIFICAÇÃO] {len(layers)} layers analisadas:")
    print(f"      ✅ Classificadas por regra: {len(layers) - len(layers_ambiguas)}")
    print(f"      ❓ Ambíguas: {len(layers_ambiguas)}")

    # ── Etapa 2: LLM para layers ambíguas ────────────────────────────────
    if layers_ambiguas and usar_llm:
        print(f"   🤖 [CLASSIFICAÇÃO] Enviando {len(layers_ambiguas)} layers para LLM...")
        try:
            mapa_llm = _classificar_via_llm(layers_ambiguas)
            for layer, categoria in mapa_llm.items():
                if categoria in CATEGORIAS_VALIDAS:
                    mapa_final[layer] = categoria
                    print(f"      LLM: '{layer}' → {categoria}")
                else:
                    print(f"      LLM: '{layer}' → categoria inválida '{categoria}', mantendo 'desconhecido'")
        except Exception as e:
            logger.warning(f"Falha na classificação LLM: {e}. Mantendo layers como 'desconhecido'.")
            print(f"   ⚠️  [CLASSIFICAÇÃO] Falha na LLM: {e}")

    return mapa_final


def _classificar_via_llm(layers: List[str]) -> Dict[str, str]:
    """
    Envia layers ambíguas para a LLM e parseia a resposta JSON.

    Inclui fallback robusto para respostas malformadas.
    """
    llm = get_chat_llm()

    prompt = PROMPT_CLASSIFICAR_LAYERS.format(layers=json.dumps(layers, ensure_ascii=False))
    resposta = llm.invoke(prompt)

    conteudo = resposta.content.strip()

    # Remove possíveis blocos de código markdown
    if conteudo.startswith("```"):
        linhas = conteudo.split("\n")
        # Remove primeira e última linha (```json e ```)
        linhas = [l for l in linhas if not l.strip().startswith("```")]
        conteudo = "\n".join(linhas)

    try:
        mapa = json.loads(conteudo)
    except json.JSONDecodeError:
        logger.warning(f"Resposta da LLM não é JSON válido: {conteudo[:200]}")
        # Tenta extrair JSON de dentro do texto
        inicio = conteudo.find("{")
        fim = conteudo.rfind("}") + 1
        if inicio >= 0 and fim > inicio:
            try:
                mapa = json.loads(conteudo[inicio:fim])
            except json.JSONDecodeError:
                return {}
        else:
            return {}

    return mapa
