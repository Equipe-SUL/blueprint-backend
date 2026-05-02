import os
from langchain_chroma import Chroma
from django.conf import settings
from apps.projetos.ai.config import get_ai_config
from apps.projetos.ai.rag.embeddings import get_embedding_model

def get_vector_store() -> Chroma:
    """Conecta ao banco vetorial ChromaDB."""
    config = get_ai_config()
    
    persist_dir = config.chroma_persist_path or os.path.join(settings.BASE_DIR, 'chroma_db')
    os.makedirs(persist_dir, exist_ok=True)
    
    return Chroma(
        collection_name="sinapi_collection",
        embedding_function=get_embedding_model(),
        persist_directory=persist_dir
    )