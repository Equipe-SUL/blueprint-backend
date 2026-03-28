import ollama

# 1. Simulando dados do cad:
dados_do_cad = """
Qtd: 50 | Unid: M | Desc: TUB PVC ESGOTO 100MM
Qtd: 12 | Unid: UN | Desc: JOELHO 90 PVC 100MM
Qtd: 20 | Unid: M2| Desc: Parede de alvenaria 15cm
"""


# 2. Prompt para direcionar o Qwen 2.5 
# Esse será o novo 'meu_prompt_magico' integrado ao RAG
prompt_rag = f"""
Você é um Engenheiro Orçamentista Militar. 
Sua tarefa é redigir um item de Memorial Descritivo técnico com base nos dados fornecidos e no contexto normativo.

[DADOS DO PROJETO]
Item: {item_nome}
Quantidade: {item_qtd} {item_unid}

[CONTEXTO NORMATIVO E PADRÃO (RECUPERADO VIA RAG)]
{contexto_recuperado} 

[REGRAS]
1. Use o parágrafo único.
2. Cite as NBRs mencionadas no contexto acima.
3. Se o contexto não mencionar uma norma específica para o item, use apenas "em conformidade com as normas técnicas vigentes".
4. Mantenha o padrão: "A quantificação de {item_qtd} {item_unid_extenso} ({item_unid})..."

Saída:
"""

print("Enviando para o Qwen pensar... (pode levar uns segundos)")

# 3. Chamando o Qwen 2.5 localmente, vem nenem
response = ollama.chat(model='qwen2.5', messages=[
  {'role': 'user', 'content': meu_prompt_magico},
])

# 4. Imprimindo a resposta do Engenheiro IA - IA boa pra hoje?
print("\n=== MEMORIAL GERADO ===\n")
print(response['message']['content'])