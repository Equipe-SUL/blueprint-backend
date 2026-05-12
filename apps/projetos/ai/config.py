from __future__ import annotations 

import os
from dataclasses import dataclass
from functools import lru_cache
from dotenv import load_dotenv
load_dotenv()

def _env_str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return default
    value = value.strip()
    return value if value else default

def _env_int(name: str, default: int) -> int:
    value = _env_str(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
  
def _env_float(name: str, default: float) -> float:
    value = _env_str(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default

def _env_bool(name: str, default: bool) -> bool:
    value = _env_str(name)
    if value is None:
        return default
    value_lower = value.lower()
    if value_lower in ['true', '1', 'yes']:
        return True
    elif value_lower in ['false', '0', 'no']:
        return False
    else:
        return default

@dataclass(frozen=True)
class AIConfig:
    ollama_base_url: str
    ollama_chat_model: str
    ollama_vl_model: str | None
    ollama_temperature: float
    langsmith_api_key: str | None
    langsmith_tracing: bool
    langsmith_project: str
    langsmith_endpoint: str
    chroma_persist_path: str | None
    embedding_model: str


def _init_langsmith_env(config: AIConfig) -> None:
    """
    Configura variáveis de ambiente que o SDK LangSmith lê automaticamente.

    Isso garante que @traceable e LangGraph enviem traces para o dashboard
    quando LANGSMITH_TRACING=true no .env.
    """
    if config.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "true"
        if config.langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = config.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = config.langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = config.langsmith_endpoint
        print(f"[CONFIG] LangSmith tracing ativado (projeto: {config.langsmith_project})")
    else:
        os.environ["LANGSMITH_TRACING"] = "false"


@lru_cache(maxsize=1)
def get_ai_config() -> AIConfig:
    config = AIConfig(
        ollama_base_url=_env_str("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_chat_model=_env_str("OLLAMA_CHAT_MODEL", "gemma4"),
        ollama_vl_model=_env_str("OLLAMA_VL_MODEL", None),
        ollama_temperature=_env_float("OLLAMA_TEMPERATURE", 0.0),
        langsmith_api_key=_env_str("LANGSMITH_API_KEY", None),
        langsmith_tracing=_env_bool("LANGSMITH_TRACING", False),
        langsmith_project=_env_str("LANGSMITH_PROJECT", "blueprint-backend"),
        langsmith_endpoint=_env_str("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
        chroma_persist_path=_env_str("CHROMA_PERSIST_PATH", None),
        embedding_model=_env_str("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
    )
    _init_langsmith_env(config)
    return config