import base64
from io import BytesIO
from PIL import Image
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from .config import get_ai_config

def analisar_imagem_com_vlm(caminho_imagem: str, alvos: list, disciplina: str = "geral") -> dict:
    """
    Analisa uma imagem de planta técnica usando o modelo VLM (MiniCPM-V).
    A análise é direcionada pela disciplina do projeto (vinda do Django Model).
    """
    config = get_ai_config()
    
    # 1. Mapeamento de Personas (Especialistas) baseado no seu Model Projeto
    # Isso ajuda a VLM a ter o contexto técnico correto
    personas = {
        'eletrica': "Engenheiro Eletricista sênior especialista em instalações prediais",
        'hidraulica': "Engenheiro Hidráulico especialista em redes de água, esgoto e drenagem",
        'alvenaria': "Engenheiro Civil e Mestre de Obras especialista em alvenaria estrutural e vedação",
        'spda': "Engenheiro especialista em Sistemas de Proteção contra Descargas Atmosféricas (Para-raios)",
        'combate_a_incendio': "Engenheiro de Segurança especialista em normas de combate a incêndio e pânico"
    }

    persona_atual = personas.get(disciplina.lower(), "Engenheiro Civil experiente")
    lista_alvos = ", ".join(alvos) if alvos else "elementos estruturais e técnicos"

    # 2. Engenharia de Prompt Dinâmica
    prompt_contextualizado = (
        f"Aja como um {persona_atual}. "
        f"Você está analisando uma planta técnica de {disciplina.upper()}. "
        f"Sua missão é identificar visualmente e listar a quantidade de: {lista_alvos}. "
        "Descreva brevemente onde esses itens estão localizados e se há alguma inconsistência visível. "
        "Seja técnico, preciso e direto ao ponto."
    )

    try:
        # 3. Processamento da Imagem
        with Image.open(caminho_imagem) as img:
            # Garantimos que a imagem está em um tamanho/formato amigável
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # 4. Configuração do Modelo VLM via Ollama
        llm_vlm = ChatOllama(
            base_url=config.ollama_base_url,
            model=config.ollama_vl_model,  # minicpm-v
            temperature=0.1 # Temperatura baixa para ser factual, não criativo
        )

        # 5. Chamada Multimodal
        print(f"[VLM] Analisando imagem como especialista em {disciplina}...")
        
        mensagem = HumanMessage(
            content=[
                {"type": "text", "text": prompt_contextualizado},
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{img_base64}",
                },
            ]
        )

        resposta = llm_vlm.invoke([mensagem])

        return {
            "sucesso": True,
            "dados": resposta.content,
            "disciplina_aplicada": disciplina,
            "erro": None
        }

    except Exception as e:
        print(f"❌ Erro na análise VLM: {str(e)}")
        return {
            "sucesso": False,
            "dados": None,
            "disciplina_aplicada": disciplina,
            "erro": str(e)
        }