from __future__ import annotations 

import os
from dataclasses import dataclass
from functools import lru_cache
from dotenv import load_dotenv
load_dotenv()

# Configuração de IA para a app projetos, utilizando variáveis de ambiente com valores default e validação.
# Necessario para converter o .env em tipos corretos e centraliza-las facilitando o acesso a essas configs.

# Retorna o valor da variável de ambiente ou o valor default se a variável não estiver definida ou for vazia.
def _env_str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return default
    value = value.strip()
    return value if value else default

# Retorna o valor da variável de ambiente como inteiro ou o valor default se a variável não estiver definida.
def _env_int(name: str, default: int) -> int:
    value = _env_str(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default

# Retorna o valor da variável de ambiente como float ou o valor default se a variável não estiver definida.    
def _env_float(name: str, default: float) -> float:
    value = _env_str(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default

# Retorna o valor da variável de ambiente como booleano ou o valor default se a variável não estiver definida.
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

# Interface de configuração, utilizando dataclass para imutabilidade e tipagem.
@dataclass(frozen=True)
class AIConfig:
    ollama_base_url: str
    ollama_chat_model: str
    ollama_vl_model: str | None
    ollama_temperature: float

# TODO: get_ai_config - decorada com lru_cache(garante que a configuração seja carregada uma vez e reutilizada em chamadas subsequentes - Otimiza a performance tbm)
@lru_cache(maxsize=1)
def get_ai_config() -> AIConfig:
    return AIConfig(
        ollama_base_url=_env_str("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_chat_model=_env_str("OLLAMA_CHAT_MODEL", "qwen2.5-coder:7b"),
        ollama_vl_model=_env_str("OLLAMA_VL_MODEL", None),
        ollama_temperature=_env_float("OLLAMA_TEMPERATURE", 0.2)
    )