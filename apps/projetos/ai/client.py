from __future__ import annotations 

from functools import lru_cache
from langchain_ollama import ChatOllama
from .config import get_ai_config

# Cliente Ollama configurado via .env e reutilizado por cache.
@lru_cache(maxsize=1)
def get_chat_llm() -> ChatOllama:
    config = get_ai_config()
    return ChatOllama(
        base_url=config.ollama_base_url,
        model=config.ollama_chat_model,
        temperature=config.ollama_temperature
    )