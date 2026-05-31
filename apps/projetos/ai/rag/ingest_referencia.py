"""
Ingere a tabela SINAPI Referência (ISD - SEM Desoneração) no ChromaDB.
Contém MATERIAIS, EQUIPAMENTOS, SERVIÇOS, MÃO DE OBRA - complementa a base existente.
"""
import os
import pandas as pd
from django.conf import settings
from langchain_core.documents import Document
from apps.projetos.ai.rag.vectorstore import get_vector_store

SINAPI_REF_FILE = "SINAPI_Referência_2025_12.xlsx"
SHEET_NAME = "ISD"  # Insumos SEM Desoneração
SKIPROWS = 9        # cabeçalho na linha 10 (0-indexed)

# Colunas do ISD após skiprows=9:
# 0: Classificação, 1: Código, 2: Descrição, 3: Unidade, 4: Origem Preço, 5+: estados


def carregar_e_vetorizar_referencia():
    caminho = os.path.join(settings.BASE_DIR, '_raw_data', SINAPI_REF_FILE)
    print(f"\n[SISTEMA] Lendo Referência: {caminho}")

    if not os.path.exists(caminho):
        print(f"[ERRO] Arquivo não encontrado: {caminho}")
        return

    try:
        df = pd.read_excel(caminho, sheet_name=SHEET_NAME, skiprows=SKIPROWS,
                           header=0, engine='openpyxl')
        df = df.fillna("")
    except Exception as e:
        print(f"[ERRO] Falha ao abrir Excel: {e}")
        return

    # Estado para preço
    estado = os.environ.get("SINAPI_ESTADO", "SP")
    colunas = list(df.columns)
    if estado in colunas:
        idx_preco = colunas.index(estado)
        print(f"[SISTEMA] Usando preços do estado: {estado} (coluna {idx_preco})")
    else:
        idx_preco = None
        print(f"[AVISO] Estado '{estado}' não encontrado. Preços não incluídos.")

    documentos = []
    pulados = 0

    print("[SISTEMA] Processando linhas da Referência...")
    for index, row in df.iterrows():
        try:
            classificacao = str(row.iloc[0]).strip()
            codigo = str(row.iloc[1]).strip()
            descricao = str(row.iloc[2]).strip()
            unidade = str(row.iloc[3]).strip()
            origem_preco = str(row.iloc[4]).strip()
        except IndexError:
            pulados += 1
            continue

        # Filtros
        if not codigo or codigo == "0" or codigo == "":
            pulados += 1
            continue
        if not descricao or descricao.lower() in ("nan", "", "0"):
            pulados += 1
            continue

        # Preço do estado
        preco_unitario = 0.0
        if idx_preco is not None:
            try:
                valor = row.iloc[idx_preco]
                if valor and str(valor).strip() not in ("", "nan", "-"):
                    preco_unitario = float(valor)
            except (ValueError, TypeError):
                pass

        grupo = classificacao.title()
        texto = (f"Grupo: {grupo} | Classificação: {classificacao} "
                 f"| Código: {codigo} | Descrição: {descricao} "
                 f"(Unidade: {unidade}) | Origem: {origem_preco}")

        metadados = {
            "codigo": codigo,
            "grupo": grupo,
            "classificacao": classificacao,
            "unidade": unidade,
            "preco_unitario": preco_unitario,
            "estado": estado,
            "origem": "sinapi_referencia",
        }

        documentos.append(Document(page_content=texto, metadata=metadados))

    print(f"\n[SISTEMA] Processados: {len(documentos)} itens válidos, {pulados} pulados.")
    print(f"Por classificação:")
    if documentos:
        from collections import Counter
        classes = Counter(d.metadata["classificacao"] for d in documentos)
        for cls, qtd in sorted(classes.items()):
            print(f"  {cls}: {qtd}")

    if not documentos:
        print("[AVISO] Nenhum item processado.")
        return

    # Ingerir no ChromaDB
    print(f"\n[SISTEMA] Gerando embeddings e salvando no ChromaDB ({len(documentos)} documentos)...")
    vector_store = get_vector_store()

    tamanho_lote = 500
    for i in range(0, len(documentos), tamanho_lote):
        lote = documentos[i:i + tamanho_lote]
        vector_store.add_documents(lote)
        print(f"  -> Progresso: {min(i + tamanho_lote, len(documentos))} de {len(documentos)}")

    print(f"\n[SUCESSO] {len(documentos)} itens da Referência SINAPI inseridos no ChromaDB!")


def limpar_e_reingerir_tudo():
    """
    Limpa a coleção ChromaDB e reingere AMBAS as bases (Mão de Obra + Referência).
    """
    vector_store = get_vector_store()
    try:
        count = vector_store._collection.count()
        print(f"[SISTEMA] Limpando coleção existente ({count} documentos)...")
        vector_store._collection.delete()
        print("[SISTEMA] Coleção limpa.")
    except Exception as e:
        print(f"[AVISO] Erro ao limpar coleção: {e}")

    # Reingerir Mão de Obra
    from apps.projetos.ai.rag.documents import carregar_e_vetorizar_sinapi
    carregar_e_vetorizar_sinapi()

    # Ingerir Referência
    carregar_e_vetorizar_referencia()


if __name__ == "__main__":
    import sys
    if "--limpar" in sys.argv:
        limpar_e_reingerir_tudo()
    else:
        carregar_e_vetorizar_referencia()
