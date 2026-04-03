from __future__ import annotations

import base64
import json
import os
from typing import Any

import requests

from .config import get_ai_config
from .prompts import VLM_SYSTEM_PROMPT, VLM_USER_PROMPT


def montar_vlm_prompt(*, disciplina: str | None, alvos: list[str]) -> str:
    if not alvos:
        raise ValueError("Lista de alvos não pode ser vazia.")
    
    alvos_limpos = [alvo.strip() for alvo in alvos if alvo and alvo.strip()]
    if not alvos_limpos:
        raise ValueError("Lista de alvos não pode conter apenas entradas vazias.")
    
    alvos_formatados = "\n".join(f"- {alvo}" for alvo in alvos_limpos)
    disciplina_txt = (disciplina or "").strip() or "geral"

    return (
        VLM_SYSTEM_PROMPT
        + "\n\n"
        + VLM_USER_PROMPT.format(disciplina=disciplina_txt, alvos_formatados=alvos_formatados)
    )

def analisar_imagem_com_vlm(
        caminho_imagem: str, 
        *,
        alvos: list[str],
        disciplina: str | None = None,
        timeout: int = 180,    
    ) -> dict[str, Any]:

    if not os.path.exists(caminho_imagem):
        return {"sucesso": False, "erro": "Arquivo de imagem não encontrado"}
    
    config = get_ai_config()
    if not config.ollama_vl_model:
        return {"sucesso": False, "erro": "Modelo de visão computacional não configurado"}
    
    try: 
        prompt = montar_vlm_prompt(disciplina=disciplina, alvos=alvos)
    except ValueError as e:
        return {"sucesso": False, "erro": f"Erro ao montar prompt: {str(e)}"}
    
    try:
        with open(caminho_imagem, "rb") as f:
            imagem_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return {"sucesso": False, "erro": f"Erro ao ler ou codificar a imagem: {str(e)}"}
    
    url = config.ollama_base_url.rstrip("/") + "/api/generate"
    payload = {
        "model": config.ollama_vl_model,
        "prompt": prompt,
        "images": [imagem_b64],
        "format": "json",
        "stream": False,
        "temperature": config.ollama_temperature,
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        raw = data.get("response" or "{}").strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)

        if not isinstance(parsed, dict):
            return {"sucesso": False, "erro": "VLM não retornou um JSON válido"}
        
        return {"sucesso": True, "dados": parsed}
    
    except requests.exceptions.RequestException as e:
        return {"sucesso": False, "erro": f"Ollama não respondeu. Erro: {str(e)}"}
    except json.JSONDecodeError:
        return {"sucesso": False, "erro": f"A IA não retornou JSON válido. Retorno bruto: {raw}"}
    except Exception as e:
        return {"sucesso": False, "erro": f"Erro inesperado: {str(e)}"}