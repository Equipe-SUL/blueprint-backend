from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import JsonOutputParser

from apps.projetos.ai.orchestration.state import WorkflowState
from apps.projetos.ai.rag.retriever import buscar_contexto_sinapi
from apps.projetos.ai.prompts import prompt_avaliacao
from apps.projetos.ai.client import get_chat_llm

def node_retrieve(state: WorkflowState):
    """Nó 1: Busca o contexto na base vetorial."""
    contexto = buscar_contexto_sinapi(state["item_cad"])
    return {"contexto_sinapi": contexto}

def node_evaluate(state: WorkflowState):
    """Nó 2: Envia os dados para a LLM principal (Gemma 4)."""
    llm = get_chat_llm()
    parser = JsonOutputParser()
    
    cadeia = prompt_avaliacao | llm | parser
    resultado = cadeia.invoke({
        "item_cad": state["item_cad"],
        "contexto_sinapi": state["contexto_sinapi"]
    })
    
    return {"decisao_gemma": resultado}

def construir_grafo_orcamento():
    """Monta e compila o fluxo do LangGraph."""
    workflow = StateGraph(WorkflowState)
    
    workflow.add_node("recuperacao", node_retrieve)
    workflow.add_node("avaliacao", node_evaluate)
    
    workflow.set_entry_point("recuperacao")
    workflow.add_edge("recuperacao", "avaliacao")
    workflow.add_edge("avaliacao", END)
    
    return workflow.compile()