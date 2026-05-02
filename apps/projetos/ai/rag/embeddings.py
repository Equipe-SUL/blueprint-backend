from functools import lru_cache
from langchain_huggingface import HuggingFaceEmbeddings
from apps.projetos.ai.config import get_ai_config

@lru_cache(maxsize=1)
def get_embedding_model() -> HuggingFaceEmbeddings:
    """Instancia o modelo multilingual e mantém-no em cache na memória."""
    config = get_ai_config()
    return HuggingFaceEmbeddings(model_name=config.embedding_model)