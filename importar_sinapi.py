import os
import argparse
import pandas as pd
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

CHROMA_PERSIST_DIR = os.path.join(os.getcwd(), "chroma_db")

def inicializar_chroma():
    print("Carregando modelo de embeddings (all-MiniLM-L6-v2)...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return Chroma(
        collection_name="base_sinapi",
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR
    )

def passar_sinapi_para_chroma(caminho_csv: str, linhas_para_pular: int, tipo_arquivo: str):
    """
    tipo_arquivo: 'insumo' (para ISD/ISE) ou 'composicao' (para CSD/CSE)
    """
    if not os.path.exists(caminho_csv):
        print(f"❌ Erro: O arquivo '{caminho_csv}' não foi encontrado.")
        return

    vector_store = inicializar_chroma()
    print(f"Lendo o arquivo: {caminho_csv} (Pulando {linhas_para_pular} linhas)...")
    
    try:
        # Lê o CSV pulando o cabeçalho da Caixa. 
        # Ajuste o separador (sep) para ',' ou ';' dependendo de como o CSV foi salvo.
        df = pd.read_csv(caminho_csv, sep=',', skiprows=linhas_para_pular, low_memory=False)
    except Exception as e:
        print(f"❌ Erro ao ler o CSV: {e}")
        return

    # Limpa nomes de colunas (tira espaços em branco extras)
    df.columns = df.columns.str.strip().str.upper()

    # Mapeamento dinâmico: A Caixa usa nomes diferentes para Insumos e Composições
    col_codigo = 'CÓDIGO DO INSUMO' if tipo_arquivo == 'insumo' else 'CÓDIGO DA COMPOSIÇÃO'
    col_desc = 'DESCRIÇÃO DO INSUMO' if tipo_arquivo == 'insumo' else 'DESCRIÇÃO DA COMPOSIÇÃO'
    col_unidade = 'UNIDADE'
    col_preco = 'PREÇO MEDIANO R$' if tipo_arquivo == 'insumo' else 'CUSTO TOTAL'

    documentos = []
    
    for index, row in df.iterrows():
        try:
            codigo = str(row.get(col_codigo, '')).strip()
            descricao = str(row.get(col_desc, '')).strip()
            
            # Se não tem descrição válida, pula a linha
            if not descricao or descricao.lower() == 'nan':
                continue

            unidade = str(row.get(col_unidade, 'un')).strip()
            
            # Tratamento rigoroso de preço (transforma "1.200,50" em 1200.50)
            preco_str = str(row.get(col_preco, '0')).replace('.', '').replace(',', '.')
            preco = float(preco_str)

            # Injetando uma disciplina padrão (como a SINAPI não tem, colocamos geral por enquanto, 
            # ou você pode criar um dicionário de palavras-chave para classificar no futuro)
            disciplina = "geral"

            conteudo_semantico = f"SINAPI {codigo} - {descricao}. Preço: R${preco:.2f} por {unidade}."

            doc = Document(
                page_content=conteudo_semantico,
                metadata={
                    "origem": "sinapi",
                    "tipo": tipo_arquivo,
                    "codigo": codigo,
                    "preco": preco,
                    "unidade": unidade,
                    "disciplina": disciplina
                }
            )
            documentos.append(doc)
            
        except Exception as e:
            # Ignora linhas de erro silenciosamente para não parar o loop (comum no fim das planilhas da Caixa)
            continue

    tamanho_lote = 1000
    print(f"Iniciando inserção de {len(documentos)} itens no ChromaDB...")
    
    for i in range(0, len(documentos), tamanho_lote):
        lote = documentos[i : i + tamanho_lote]
        vector_store.add_documents(lote)
        print(f"✅ Lote {(i//tamanho_lote) + 1} salvo.")

    print(f"🚀 Sucesso! Dados salvos na pasta '{CHROMA_PERSIST_DIR}'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", help="Caminho para o CSV")
    parser.add_argument("--skip", type=int, default=5, help="Número de linhas para pular no topo")
    parser.add_argument("--tipo", choices=['insumo', 'composicao'], required=True, help="Tipo do catálogo")
    args = parser.parse_args()
    
    passar_sinapi_para_chroma(args.csv, args.skip, args.tipo)