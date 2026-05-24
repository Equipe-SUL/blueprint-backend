"""
Substitui a busca embeddings por: keyword filter + LLM (gemma4) para matching SINAPI.
"""
import os, re, json
import pandas as pd
from django.conf import settings
from langchain_core.messages import SystemMessage, HumanMessage
from apps.projetos.ai.client import get_chat_llm

# Cache do DataFrame SINAPI Referência
_SINAPI_REF_DF = None

SINAPI_REF_FILE = "SINAPI_Referência_2025_12.xlsx"

def _carregar_df():
    global _SINAPI_REF_DF
    if _SINAPI_REF_DF is not None:
        return _SINAPI_REF_DF
    caminho = os.path.join(settings.BASE_DIR, '_raw_data', SINAPI_REF_FILE)
    df = pd.read_excel(caminho, sheet_name='ISD', skiprows=9, header=0, engine='openpyxl')
    df = df.fillna("")
    estado = os.environ.get("SINAPI_ESTADO", "SP")
    colunas = list(df.columns)
    idx_preco = colunas.index(estado) if estado in colunas else None
    _SINAPI_REF_DF = (df, idx_preco, estado)
    print(f"[SINAPI] DataFrame carregado: {len(df)} linhas, estado={estado}, col_preco={idx_preco}")
    return _SINAPI_REF_DF


def buscar_por_palavras_chave(descricao: str, top_k: int = 10) -> list:
    """
    Filtra a SINAPI Referência por palavras-chave extraídas da descrição.
    Retorna os top_k itens mais relevantes.

    Melhorias:
    - Bigrams para capturar termos compostos (ex: "maquina de lavar", "caixa acoplada")
    - Primeira palavra-chave tem peso dobrado (é o tipo do item)
    - Penaliza descrições CAD muito longas que geram keywords genéricas demais
    """
    df, idx_preco, estado = _carregar_df()

    stopwords = {'com', 'para', 'em', 'de', 'da', 'do', 'das', 'dos', 'um', 'uma',
                 'e', 'ou', 'a', 'o', 'as', 'os', 'na', 'no', 'nas', 'nos',
                 'por', 'sem', 'x', 'tipo', 'comprimento', 'largura', 'altura'}

    desc_lower = descricao.lower()
    palavras = re.findall(r'[a-zA-Z\u00C0-\u00FF]{3,}', desc_lower)
    keywords = [p for p in palavras if p not in stopwords]

    if not keywords:
        return []

    # Gerar bigrams: pares de palavras consecutivas
    todos_termos = list(keywords)
    for i in range(len(keywords) - 1):
        bigram = f"{keywords[i]} {keywords[i+1]}"
        if bigram not in todos_termos:
            todos_termos.append(bigram)

    desc_col = df.iloc[:, 2].str.lower()

    # OR filter: qualquer keyword acha candidato inicial
    mask_or = desc_col.str.contains('|'.join(keywords), na=False)
    candidatos = df[mask_or].copy()

    if len(candidatos) == 0:
        return []

    def score_row(row):
        desc = str(row.iloc[2]).lower()
        s = 0
        # Bigrams pesam mais (termos compostos)
        for termo in todos_termos:
            if " " in termo:
                # bigram: +3 se encontrado
                if termo in desc:
                    s += 3
            else:
                if termo in desc:
                    # primeira keyword do item CAD vale mais
                    if termo == keywords[0]:
                        s += 2
                    else:
                        s += 1
        # Penalidade: se so 1 keyword curta (ex: "pia" 3 letras) der match em descricao muito diferente
        if s <= 1 and len(keywords) >= 2:
            s -= 2
        return s

    candidatos['_score'] = candidatos.apply(score_row, axis=1)

    # Remover candidatos com score 0 (só passou pelo OR filter mas sem match real)
    candidatos = candidatos[candidatos['_score'] > 0]

    if len(candidatos) == 0:
        return []

    candidatos = candidatos.sort_values('_score', ascending=False)

    resultados = []
    for _, row in candidatos.head(top_k).iterrows():
        preco = 0.0
        if idx_preco is not None:
            try:
                val = row.iloc[idx_preco]
                if val and str(val).strip() not in ("", "nan", "-"):
                    preco = float(val)
            except (ValueError, TypeError):
                pass
        resultados.append({
            "codigo": str(row.iloc[1]).strip(),
            "grupo": str(row.iloc[0]).strip(),
            "descricao": str(row.iloc[2]).strip(),
            "unidade": str(row.iloc[3]).strip(),
            "preco_unitario": preco,
            "_score": int(row['_score']),
        })
    return resultados


# Prompt para o LLM escolher o código SINAPI
PROMPT_SINAPI_MATCH = """\
Você é um engenheiro civil especialista em orçamento e composição de custos da SINAPI.

Dado um item extraído de um projeto CAD/DXF, escolha o código SINAPI mais adequado
da lista de candidatos fornecida.

ITEM CAD:
{descricao_cad}
Categoria: {categoria}
Quantidade: {quantidade}
Unidade: {unidade}

CANDIDATOS SINAPI:
{candidatos}

INSTRUÇÕES:
1. Analise a descrição do item CAD e compare com cada candidato SINAPI.
2. Escolha o candidato que melhor corresponde em termos de MATERIAL, SERVIÇO ou MÃO DE OBRA.
3. Para equipamentos (fogão, máquina de lavar, etc.), prefira candidatos da classificação MATERIAL.
4. Para louças e metais (bacia, lavatório, pia, chuveiro), prefira MATERIAL.
5. REGRA CRÍTICA - Priorize itens COMPLETOS sobre itens PARCIAIS:
    - Se a descrição CAD for "Porta de madeira" e houver "KIT PORTA PRONTA" disponível, PREFIRA o kit (inclui folha + batente + guarnições) em vez de apenas "PORTA DE MADEIRA/FOLHA" (item avulso)
    - Se houver "JANELA" completa, prefira sobre acessórios/componentes avulsos
    - Se a descrição for "Chuveiro" e houver "CHUVEIRO COMUM" (chuveiro completo), prefira sobre acessórios como "BRAÇO PARA CHUVEIRO"
    - Se a descrição for "Lavatório" e houver "LAVATORIO/CUBA DE EMBUTIR", prefira sobre "ABERTURA PARA ENCAIXE DE CUBA" (serviço)
6. Para itens de louça (bacia, lavatório, cuba, pia), metais (chuveiro, torneira) e materiais de acabamento (piso, revestimento), aceite o melhor candidato MATERIAL mesmo que seja apenas o material (sem mão de obra). Justifique como "MATERIAL — requer mão de obra para instalação".
7. NUNCA aceite um candidato claramente incompatível (ex: ar-condicionado para piso, cabo elétrico para telhado).
8. Retorne APENAS um JSON válido:
{{
    "codigo_escolhido": "código SINAPI",
    "descricao_escolhida": "descrição completa do SINAPI",
    "justificativa": "explicação curta",
    "confianca": "alta/media/baixa"
}}

Se nenhum candidato for adequado, retorne:
{{
    "codigo_escolhido": null,
    "descricao_escolhida": null,
    "justificativa": "Nenhum candidato SINAPI compatível encontrado",
    "confianca": "baixa"
}}
"""


# ── Estimativas de custo para serviços sem código SINAPI direto ────────────
# Baseadas em CUB (Custo Unitário Básico) e composições SINAPI típicas
# Valores por m² (salvo indicação), incluem MATERIAL + MÃO DE OBRA
ESTIMATIVAS_SERVICOS = [
    (["alvenaria", "vedacao", "parede", "bloco"], "Alvenaria de vedação (blocos + argamassa + mão de obra)", 72.00, "M2"),
    (["alvenaria", "estrutural"], "Alvenaria estrutural (blocos + argamassa + mão de obra)", 95.00, "M2"),
    (["contrapiso"], "Contrapiso regularizado (argamassa + mão de obra)", 42.00, "M2"),
    (["reboco", "emboço"], "Reboco/emboço parede interna (argamassa + mão de obra)", 32.00, "M2"),
    (["chapisco"], "Chapisco paredes (argamassa + mão de obra)", 12.00, "M2"),
    (["pintura", "latex", "acrilica"], "Pintura de parede interna (massa + tinta + mão de obra)", 22.00, "M2"),
    (["piso", "ceramico", "porcelanato"], "Piso cerâmico/porcelanato (material + argamassa + rejunte + mão de obra)", 68.00, "M2"),
    (["telhado", "cobertura", "telha"], "Telhado (estrutura + telhas + mão de obra)", 210.00, "M2"),
    (["laje", "premoldada"], "Laje pré-moldada (vigotas + lajotas + concreto + mão de obra)", 130.00, "M2"),
    (["esquadria", "aluminio"], "Esquadria de alumínio (fornecimento + instalação)", 450.00, "M2"),
    (["esquadria", "madeira"], "Esquadria de madeira (fornecimento + instalação)", 350.00, "M2"),
    (["porta", "madeira"], "Porta de madeira completa (kit + batente + guarnições + instalação)", 380.00, "UN"),
    (["janela", "aluminio"], "Janela de alumínio (fornecimento + instalação)", 420.00, "M2"),
    (["hidraulica", "hidrossanitario", "agua", "esgoto"], "Instalação hidráulica completa (água + esgoto)", 85.00, "M2"),
    (["eletrica", "instalacao"], "Instalação elétrica completa (pontos + fiação + quadro)", 65.00, "M2"),
    (["pilar", "concreto"], "Pilar de concreto armado (concreto + aço + forma + mão de obra)", 1000.00, "M3"),
    (["viga", "concreto"], "Viga de concreto armado (concreto + aço + forma + mão de obra)", 950.00, "M3"),
    (["concreto", "armado", "estrutural"], "Concreto armado estrutural (concreto + aço + forma + mão de obra)", 800.00, "M3"),
    (["estaca", "concreto"], "Estaca de concreto armado (concreto + aço + execução)", 650.00, "M3"),
    (["fundacao", "sapata", "radier"], "Fundação (concreto + aço + forma + mão de obra)", 420.00, "M3"),
]


def match_com_llm(descricao_cad: str, categoria: str = "",
                  quantidade: float = 0, unidade: str = "") -> dict:
    """
    Usa o LLM (gemma4) para escolher o melhor código SINAPI.
    1. Verifica estimativas CUB para serviços de construção civil
    2. Se for mobília, retorna sem match
    3. Filtra SINAPI por palavras-chave
    4. Envia candidatos para o LLM
    5. Retorna o resultado
    """
    desc_lower = descricao_cad.lower()

    # 0. Mobília — não tem na SINAPI
    PALAVRAS_MOBILIA = ["cama", "sofa", "geladeira", "televisao", "tv", "mesa", "vaso",
                        "planta", "vegetação", "vegetacao", "ornamental", "armario",
                        "guarda-roupa", "cadeira", "poltrona", "tapete", "cortina",
                        "maquina de lavar", "fogao"]
    if any(p in desc_lower for p in PALAVRAS_MOBILIA):
        return {
            "codigo_escolhido": None,
            "descricao_escolhida": None,
            "justificativa": "Item de mobília/equipamento doméstico — não faz parte da SINAPI (fornecer pelo proprietário)",
            "confianca": "baixa",
            "candidatos": [],
        }

    # 0.5. Hachura/hatch — elemento gráfico, não item construtivo
    if "hach" in desc_lower or "hatch" in desc_lower:
        return {
            "codigo_escolhido": None,
            "descricao_escolhida": None,
            "justificativa": "Hachura/hatch — elemento gráfico do desenho, não item de construção civil",
            "confianca": "baixa",
            "candidatos": [],
        }

    # 0.6. Contorno/perímetro — apenas referência topográfica
    if desc_lower in ("contorno", "perímetro", "perimetro", "limite", "divisa"):
        return {
            "codigo_escolhido": None,
            "descricao_escolhida": None,
            "justificativa": "Contorno/perímetro do terreno — referência topográfica, não item de construção",
            "confianca": "baixa",
            "candidatos": [],
        }

    # 1. Estimativa CUB para serviços de construção sem código SINAPI direto
    #    Usa score de matching: primeira keyword obrigatória, depois razão de acerto
    melhores = []
    for palavras, desc_est, preco_est, un_est in ESTIMATIVAS_SERVICOS:
        # Primeira keyword deve SEMPRE estar presente (é a mais específica)
        if palavras[0] not in desc_lower:
            continue
        # Conta quantas keywords bateram
        acertos = sum(1 for p in palavras if p in desc_lower)
        ratio = acertos / len(palavras)
        melhores.append((ratio, preco_est, un_est, desc_est, palavras))

    if melhores:
        melhores.sort(key=lambda x: (-x[0], -x[1]))  # maior ratio, depois maior preço
        melhor = melhores[0]
        ratio, preco_est, un_est, desc_est, palavras = melhor
        if ratio >= 0.4:  # pelo menos 40% das keywords
            return {
                "codigo_escolhido": f"EST-{palavras[0].upper()}",
                "descricao_escolhida": f"{desc_est} (R$ {preco_est:.2f}/{un_est})",
                "justificativa": f"ESTIMATIVA CUB — {desc_est}. SINAPI não possui código de serviço completo. Inclui material + mão de obra.",
                "confianca": "media",
                "candidatos": [],
                "_preco_estimado": preco_est,
                "_unidade_estimada": un_est,
                "_tipo_estimativa": "CUB",
            }

    # 2. Busca candidatos SINAPI via keyword filter
    candidatos = buscar_por_palavras_chave(descricao_cad, top_k=20)
    if not candidatos:
        return {
            "codigo_escolhido": None,
            "descricao_escolhida": None,
            "justificativa": "Nenhum candidato SINAPI encontrado por palavra-chave",
            "confianca": "baixa",
            "candidatos": [],
        }

    # Montar texto dos candidatos
    cand_texto = ""
    for i, c in enumerate(candidatos, 1):
        cand_texto += f"{i}. Código: {c['codigo']} | Grupo: {c['grupo']} | "
        cand_texto += f"Descrição: {c['descricao']} | Unidade: {c['unidade']} | "
        cand_texto += f"Preço: R$ {c['preco_unitario']:.2f}\n"

    prompt = PROMPT_SINAPI_MATCH.format(
        descricao_cad=descricao_cad,
        categoria=categoria,
        quantidade=quantidade,
        unidade=unidade or "un",
        candidatos=cand_texto,
    )

    try:
        llm = get_chat_llm()
        mensagens = [
            SystemMessage(
                content="Você é um especialista em orçamento de obras e composições SINAPI."
            ),
            HumanMessage(content=prompt),
        ]
        resposta = llm.invoke(mensagens)
        texto = resposta.content.strip()

        # Parse JSON
        if "```json" in texto:
            texto = texto.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in texto:
            texto = texto.split("```", 1)[1].split("```", 1)[0]
        resultado = json.loads(texto.strip())
        resultado["candidatos"] = candidatos

        return resultado
    except Exception as e:
        return {
            "codigo_escolhido": None,
            "descricao_escolhida": None,
            "justificativa": f"Erro no LLM: {e}",
            "confianca": "baixa",
            "candidatos": candidatos,
        }


# Teste rápido
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
    import django; django.setup()

    descricoes_teste = [
        "Bacia sanitária",
        "Lavatório com bancada e cuba redonda",
        "Pia de cozinha 120x55cm",
        "Porta de madeira 0.80x2.10",
        "Fogão 4 bocas",
        "Tanque de lavar 50x50cm",
        "Chuveiro elétrico",
        "Máquina de lavar 10kg",
        "Box de banho 80cm",
        "Janela de ventilação 0.60x0.60",
        "Pilar de concreto armado",
        "Alvenaria de vedação",
    ]

    for desc in descricoes_teste:
        print(f"\n--- {desc} ---")

        # 1. Keyword filter
        cands = buscar_por_palavras_chave(desc, top_k=5)
        print(f"  Keyword filter: {len(cands)} candidatos")
        for c in cands[:3]:
            print(f"    [{c['codigo']}] {c['descricao'][:60]} - R$ {c['preco_unitario']:.2f}")

        # 2. LLM match
        # (descomentar para testar com LLM real - requer chamada à API)
        # resultado = match_com_llm(desc)
        # print(f"  LLM escolheu: {resultado.get('codigo_escolhido')} (confianca: {resultado.get('confianca')})")
