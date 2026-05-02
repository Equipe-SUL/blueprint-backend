import os
import pandas as pd
from langchain_core.documents import Document
from django.conf import settings
from apps.projetos.ai.rag.vectorstore import get_vector_store

def carregar_e_vetorizar_sinapi(nome_arquivo: str = "SINAPI_mao_de_obra_2025_12.xlsx"):
    """
    Lê a base da SINAPI através do arquivo de Mão de Obra, pois o arquivo
    de Referência (CSD) da Caixa vem com códigos zerados.
    Este arquivo possui a mesma estrutura e os códigos intactos!
    """
    
    caminho_xlsx = os.path.join(settings.BASE_DIR, '_raw_data', nome_arquivo)
    
    print(f"\n[SISTEMA] Iniciando leitura da base corrigida em:\n{caminho_xlsx}")
    
    if not os.path.exists(caminho_xlsx):
        print(f"\n[ERRO] Arquivo não encontrado: {caminho_xlsx}")
        return

    try:
        # O arquivo de Mão de Obra tem o cabeçalho na linha 6 (skiprows=5)
        # A aba chama-se 'SEM Desoneração'
        df = pd.read_excel(
            caminho_xlsx, 
            sheet_name='SEM Desoneração', 
            skiprows=5, 
            engine='openpyxl'
        )
        df = df.fillna("")
    except Exception as e:
        print(f"\n[ERRO] Falha ao abrir o Excel: {e}")
        return
    
    documentos = []
    
    print("[SISTEMA] Processando linhas da planilha (buscando Códigos Reais)...")
    for index, row in df.iterrows():
        try:
            grupo = str(row.iloc[0]).strip()
            codigo = str(row.iloc[1]).strip()
            descricao = str(row.iloc[2]).strip()
            unidade = str(row.iloc[3]).strip()
        except IndexError:
            continue
            
        # O FILTRO DEFINITIVO: Se o código for "0" ou vazio, o robô ignora!
        if not descricao or descricao.lower() == "nan" or descricao == "0" or not codigo or codigo == "0":
            continue
            
        texto_para_vetor = f"Grupo: {grupo} | Código: {codigo} | Descrição: {descricao} (Unidade: {unidade})"
        
        metadados = {
            "codigo": codigo,
            "grupo": grupo,
            "unidade": unidade,
            "origem": "sinapi_mao_de_obra"
        }
        
        documentos.append(Document(page_content=texto_para_vetor, metadata=metadados))

    if documentos:
        print(f"\n[SISTEMA] SUCESSO: {len(documentos)} itens com CÓDIGOS VÁLIDOS extraídos.")
        print("[SISTEMA] Gerando embeddings e salvando no ChromaDB. Aguarde...")
        
        vector_store = get_vector_store()
        
        tamanho_lote = 1000
        for i in range(0, len(documentos), tamanho_lote):
            lote = documentos[i:i + tamanho_lote]
            vector_store.add_documents(lote)
            print(f" -> Progresso: {i + len(lote)} de {len(documentos)} itens.")
            
        print("\n[SUCESSO] O RAG agora possui o conhecimento total e com CÓDIGOS REAIS!")
    else:
        print("\n[AVISO] Nenhum dado processado.")