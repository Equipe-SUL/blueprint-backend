from __future__ import annotations
from typing import Any

from .vision import analisar_imagem_com_vlm
from .interpretation import interpretar_itens_extraidos_dxf

def processar_planta_completa(
    caminho_imagem: str, 
    json_dxf: dict[str, Any], 
    tipo_projeto: list[str], 
    alvos_visao: list[str]
) -> Any:
    """
    O Cérebro do sistema. Ele orquestra a VLM, o RAG e a LLM na ordem correta.
    """
    print("\n[Orquestrador] 👁️ Passo 1: VLM analisando a imagem da planta...")
    resultado_visao = analisar_imagem_com_vlm(
        caminho_imagem=caminho_imagem,
        alvos=alvos_visao,
        disciplina=tipo_projeto[0] if tipo_projeto else "geral"
    )

    contexto_visual = "Nenhuma análise visual disponível."
    if resultado_visao.get("sucesso"):
        contexto_visual = resultado_visao.get("dados")
        print(f"[Orquestrador] ✅ VLM encontrou: {contexto_visual}")
    else:
        print(f"[Orquestrador] ⚠️ Aviso Visual: {resultado_visao.get('erro')}")

    print("\n[Orquestrador] 🧠 Passo 2: Injetando a Visão no cérebro do Qwen...")
    # Aqui é onde a magia acontece: colocamos o que a VLM viu dentro do JSON que vai pro Qwen
    json_dxf["analise_visual"] = contexto_visual

    print("[Orquestrador] 📊 Passo 3: RAG e LLM processando os preços e cruzando os dados...")
    resultado_final = interpretar_itens_extraidos_dxf(
        itens_extraidos=json_dxf,
        tipo_projeto=tipo_projeto
    )

    print("\n[Orquestrador] 🎉 Sucesso! Orçamento concluído.")
    return resultado_final