import sys
import os
import django
import pandas as pd

# Configuração do Django para poderes usar os módulos (ajusta o nome 'setup' se necessário)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from apps.projetos.ai.rag.embeddings import ingerir_documentos_sinapi, get_vector_store

def teste_ingestao_excel(caminho_excel: str):
    """Lê as primeiras 50 linhas do Excel da SINAPI e insere no ChromaDB."""
    print(f"A ler o Excel: {caminho_excel}")
    # Nota: Ajusta as colunas de acordo com o formato real da tua planilha SINAPI
    df = pd.read_excel(caminho_excel, skiprows=6) # Muitas vezes a SINAPI tem cabeçalhos complexos
    
    # Pega apenas uma amostra para teste rápido
    df_amostra = df.head(50).fillna("") 
    
    itens_para_inserir = []
    for index, row in df_amostra.iterrows():
        # Estes nomes de colunas ('CODIGO', 'DESCRICAO', etc) têm de bater certo com o teu Excel
        # Tenta imprimir um print(df.columns) se tiveres dúvidas
        item = {
            "codigo": str(row.get("CÓDIGO DA COMPOSIÇÃO", "S/N")),
            "descricao": str(row.get("DESCRIÇÃO DA COMPOSIÇÃO", "S/D")),
            "unidade": str(row.get("UNIDADE", "-")),
            "grupo": "A DEFINIR", # Ajusta se tiveres a coluna do grupo
            "preco": 0.0 # Ajusta para a coluna de custo com desoneração ou não desoneração
        }
        # Só insere se tiver uma descrição válida
        if item["descricao"] and item["descricao"] != "S/D":
            itens_para_inserir.append(item)
            
    print(f"Foram formatados {len(itens_para_inserir)} itens para inserção.")
    ingerir_documentos_sinapi(itens_para_inserir)

def teste_busca_semantica(termo_busca: str):
    """Testa se o banco devolve os resultados esperados para um termo de busca."""
    print(f"\n--- A realizar busca por: '{termo_busca}' ---")
    vector_store = get_vector_store()
    
    # Fazemos a busca pelos 3 mais parecidos
    resultados = vector_store.similarity_search(termo_busca, k=3)
    
    for i, doc in enumerate(resultados, 1):
        print(f"\nResultado {i}:")
        print(f"Texto Vetorizado: {doc.page_content}")
        print(f"Metadados associados: {doc.metadata}")
        
if __name__ == "__main__":
    # 1. Pega no caminho do ficheiro que partilhaste
    caminho_tabela_sinapi = "_raw_data/SINAPI_Refer ncia_2025_12.xlsx"
    
    # 2. Faz a ingestão (podes comentar esta linha depois de rodares a primeira vez)
    teste_ingestao_excel(caminho_tabela_sinapi)
    
    # 3. Testa a tua busca com termos como se fossem os gerados pelo CAD
    teste_busca_semantica("bloco concreto estrutural")
    teste_busca_semantica("tubo PVC 40mm esgoto")