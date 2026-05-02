from langchain_core.prompts import PromptTemplate

PROMPT_GESTOR_ORCAMENTO = """
Você é um engenheiro orçamentista avaliando quantitativos para um memorial técnico.
O sistema extraiu o seguinte item da planta CAD:

ITEM DO CAD:
{item_cad}

O nosso banco de dados RAG retornou os seguintes itens da tabela SINAPI que podem ser correspondentes:

CONTEXTO SINAPI:
{contexto_sinapi}

Sua tarefa:
1. Analise o item do CAD e os itens fornecidos pelo contexto SINAPI.
2. Identifique qual código SINAPI é a correspondência EXATA para o item do CAD.
3. Retorne APENAS um JSON válido no seguinte formato, sem blocos de código (```json) ou texto extra:
{{
    "codigo_sinapi_escolhido": "12345",
    "justificativa_breve": "motivo técnico da escolha",
    "confianca": "alta/media/baixa"
}}

Se nenhum item for minimamente compatível, retorne "codigo_sinapi_escolhido": null.
"""

prompt_avaliacao = PromptTemplate(
    template=PROMPT_GESTOR_ORCAMENTO,
    input_variables=["item_cad", "contexto_sinapi"]
)