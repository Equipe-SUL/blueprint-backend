import os
import json
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from django.conf import settings

# Caminho físico onde o banco vetorial será salvo dentro do seu projeto Django
CHROMA_PERSIST_DIR = os.path.join(settings.BASE_DIR, "chroma_db")

def get_embeddings_model():
    """Retorna o modelo que transforma texto em vetores.
    O all-MiniLM-L6-v2 é muito rápido, leve e excelente para rodar localmente.
    """
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def popular_banco_sinapi_teste(vector_store: Chroma):
    """
    Função utilitária para injetar dados falsos da SINAPI apenas para validar a PoC.
    No futuro, vocês podem ler um CSV real aqui.
    """
    dados_mock = [
        {"codigo": "73942/002", "descricao": "Concreto usinado bombeavel fck 25 MPa", "preco": 450.00, "unidade": "m3"},
        {"codigo": "92873", "descricao": "Armacao de pilar ou viga baldrame aco CA-50", "preco": 12.00, "unidade": "kg"},
        {"codigo": "12345", "descricao": "Caixa de inspecao em alvenaria", "preco": 150.00, "unidade": "un"},
        {"codigo": "54321", "descricao": "Tubo PVC Esgoto 100mm", "preco": 35.00, "unidade": "m"}
    ]
    
    documentos = []
    for item in dados_mock:
        # O 'page_content' é o que a IA vai ler. O 'metadata' são dados de apoio.
        conteudo = f"SINAPI {item['codigo']}: {item['descricao']} - Preço: R${item['preco']} por {item['unidade']}"
        doc = Document(page_content=conteudo, metadata={"origem": "sinapi", "preco": item["preco"], "unidade": item["unidade"]})
        documentos.append(doc)
    
    vector_store.add_documents(documentos)
    print("Banco SINAPI populado com sucesso!")

def get_vector_store() -> Chroma:
    """
    Carrega o banco de dados ChromaDB. 
    Se ele estiver vazio, injeta nossos dados de teste automaticamente.
    """
    embeddings = get_embeddings_model()
    
    # Inicializa o banco apontando para a pasta persistente
    vector_store = Chroma(
        collection_name="base_sinapi",
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR
    )
    
    # Se o banco acabou de ser criado e está vazio, nós o populamos
    # Em produção, você comentaria essa validação após a carga inicial.
    try:
        if vector_store._collection.count() == 0:
            popular_banco_sinapi_teste(vector_store)
    except Exception as e:
        print(f"Erro ao verificar contagem do banco: {e}")
        
    return vector_store