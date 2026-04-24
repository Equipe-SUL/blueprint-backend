import base64
import json
import re
from io import BytesIO
from PIL import Image
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from .config import get_ai_config
from .prompts import VLM_SYSTEM_PROMPT, VLM_USER_PROMPT_TEMPLATE, ALVENARIA_VISUAL_TARGETS


def _validar_e_limpar_json_vlm(texto: str) -> dict:
    """
    Callback de validação: Limpa marcações markdown e tenta fazer o parse do JSON.
    Garante que a saída seja sempre um dicionário Python válido (CA.4).
    """
    try:
        # Remove blocos markdown (```json e ```) que a LLM costuma colocar
        texto_limpo = re.sub(r'```json\s*', '', texto, flags=re.IGNORECASE)
        texto_limpo = re.sub(r'```\s*', '', texto_limpo)
        texto_limpo = texto_limpo.strip()
        
        return json.loads(texto_limpo)
    except json.JSONDecodeError as e:
        raise ValueError(f"Falha ao decodificar JSON da VLM: {str(e)} | Resposta Bruta: {texto[:100]}...")



def analisar_imagem_com_vlm(caminho_imagem: str) -> dict:
    """
    Analisa uma imagem de planta técnica focado EXCLUSIVAMENTE em Alvenaria (RN.1).
    """
    config = get_ai_config()
    
    # 1. Engenharia de Prompt Focada em Alvenaria
    prompt_contextualizado = VLM_USER_PROMPT_TEMPLATE.format(
        alvos_alvenaria=", ".join(ALVENARIA_VISUAL_TARGETS)
    )

    try:
        # 2. Processamento da Imagem
        with Image.open(caminho_imagem) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # 3. Configuração do Modelo VLM via Ollama
        llm_vlm = ChatOllama(
            base_url=config.ollama_base_url,
            model=config.ollama_vl_model,  # minicpm-v
            temperature=0.0 # Temperatura ZERO para ser estritamente técnico e determinístico
        )

        print("[VLM] Analisando imagem com foco EXCLUSIVO em Alvenaria...")
        
        # 4. Chamada Multimodal (Usando System Message separado para dar mais autoridade)
        mensagens = [
            SystemMessage(content=VLM_SYSTEM_PROMPT),
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt_contextualizado},
                    {"type": "image_url", "image_url": f"data:image/jpeg;base64,{img_base64}"},
                ]
            )
        ]

        resposta = llm_vlm.invoke(mensagens)

        # 5. Validação Callback do JSON (Trata erros graciosamente)
        dados_json = _validar_e_limpar_json_vlm(resposta.content)

        return {
            "sucesso": True,
            "dados": dados_json,
            "disciplina_aplicada": "alvenaria",
            "erro": None
        }

    except Exception as e:
        print(f"❌ Erro na análise VLM: {str(e)}")
        return {
            "sucesso": False,
            "dados": {},
            "disciplina_aplicada": "alvenaria",
            "erro": str(e)
        }