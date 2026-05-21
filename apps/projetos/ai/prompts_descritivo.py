"""
prompts_descritivo.py
=====================
Prompts especializados para o agente LLM auditor que gera o Memorial Descritivo.

O agente atua como um engenheiro civil auditor, cruzando os dados extraídos
do DXF com os metadados da obra para produzir um memorial técnico estruturado.
"""

# ── System Prompt: Define o papel do agente ──────────────────────────────────

SYSTEM_PROMPT_AUDITOR = """\
Você é um engenheiro civil sênior especializado em laudos e memoriais técnicos \
de construção civil. Sua função é atuar como AUDITOR: receber dados brutos \
extraídos de uma planta baixa em formato DXF (AutoCAD) e produzir um \
Memorial Descritivo completo, técnico e formatado.

Regras:
1. Analise TODOS os dados fornecidos: ambientes, camadas (layers), entidades \
   geométricas, textos de legenda e metadados da obra.
2. IDENTIFIQUE inconsistências (ex: ambiente sem nome, parede sem porta de \
   acesso, cômodo com área incompatível, elementos estruturais ausentes).
3. NÃO invente dados que não estejam na extração. Se uma informação não estiver \
   disponível, registre como "não identificado na planta".
4. Retorne APENAS um JSON válido, sem markdown, sem blocos de código, sem \
   texto extra antes ou depois do JSON.
5. Utilize terminologia técnica da engenharia civil brasileira (NBRs).
"""

# ── User Prompt: Template com os dados da extração ──────────────────────────

USER_PROMPT_MEMORIAL_DESCRITIVO = """\
Com base nos dados extraídos da planta baixa DXF abaixo, gere o Memorial Descritivo \
completo da obra.

═══════════════════════════════════════════════════════════════
METADADOS DA OBRA:
═══════════════════════════════════════════════════════════════
{metadados_obra}

═══════════════════════════════════════════════════════════════
AMBIENTES IDENTIFICADOS (via MTEXT do CAD):
═══════════════════════════════════════════════════════════════
{ambientes}

═══════════════════════════════════════════════════════════════
TEXTOS DE LEGENDA (anotações encontradas na planta):
═══════════════════════════════════════════════════════════════
{textos_legenda}

═══════════════════════════════════════════════════════════════
RESUMO POR CAMADA (quantitativos por layer do DXF):
═══════════════════════════════════════════════════════════════
{resumo_por_camada}

═══════════════════════════════════════════════════════════════
ESTATÍSTICAS GERAIS DA EXTRAÇÃO:
═══════════════════════════════════════════════════════════════
{estatisticas}

═══════════════════════════════════════════════════════════════
INSTRUÇÕES DE SAÍDA:
═══════════════════════════════════════════════════════════════
Retorne APENAS um JSON válido com a seguinte estrutura:
{{
    "dados_gerais": {{
        "nome_obra": "...",
        "localizacao": "...",
        "tipo_construcao": "...",
        "padrao_acabamento": "...",
        "descricao_geral": "Texto descritivo geral do empreendimento..."
    }},
    "ambientes": [
        {{
            "nome": "Sala de Estar",
            "area_m2": 15.5,
            "perimetro_m": 16.0,
            "pe_direito_m": 3.0,
            "descricao": "Ambiente com área de 15.5m², pé-direito de 3.0m...",
            "elementos_identificados": ["parede de alvenaria", "esquadria"],
            "observacoes": "..."
        }}
    ],
    "elementos_estruturais": {{
        "fundacoes": {{
            "descricao": "...",
            "quantidade": 0,
            "area_total_m2": 0.0,
            "observacoes": "..."
        }},
        "pilares": {{
            "descricao": "...",
            "quantidade": 0,
            "area_total_m2": 0.0,
            "observacoes": "..."
        }},
        "vigas": {{
            "descricao": "...",
            "quantidade": 0,
            "comprimento_total_m": 0.0,
            "observacoes": "..."
        }},
        "lajes": {{
            "descricao": "...",
            "quantidade": 0,
            "area_total_m2": 0.0,
            "observacoes": "..."
        }},
        "paredes": {{
            "descricao": "...",
            "quantidade": 0,
            "area_total_m2": 0.0,
            "comprimento_total_m": 0.0,
            "area_liquida_m2": 0.0,
            "volume_m3": 0.0,
            "observacoes": "..."
        }},
        "esquadrias": {{
            "descricao": "...",
            "quantidade": 0,
            "observacoes": "..."
        }}
    }},
    "instalacoes": {{
        "hidrossanitario": {{
            "descricao": "...",
            "identificado": true,
            "detalhes": "..."
        }},
        "eletrica": {{
            "descricao": "...",
            "identificado": false,
            "detalhes": "..."
        }}
    }},
    "observacoes_tecnicas": [
        "Observação técnica 1...",
        "Observação técnica 2..."
    ],
    "inconsistencias_detectadas": [
        "Inconsistência 1...",
        "Inconsistência 2..."
    ],
    "confianca_analise": "alta"
}}

IMPORTANTE:
- Preencha TODOS os campos com base nos dados fornecidos.
- Para campos numéricos, use os valores extraídos do DXF.
- Para descrições, use linguagem técnica formal.
- Em "confianca_analise", use "alta" se os dados são completos e coerentes, \
  "media" se faltam algumas informações, ou "baixa" se há muitas lacunas.
- Em "inconsistencias_detectadas", liste TODAS as anomalias encontradas.
"""
