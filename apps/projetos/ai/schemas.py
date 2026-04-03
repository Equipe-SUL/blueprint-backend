from typing import List, Optional
from pydantic import BaseModel, Field

class ItemOrcamento(BaseModel):
    """
    Representa um item individual de orçamento extraído e processado.
    """
    descricao: str = Field(
        description="Descrição detalhada do item, preferencialmente seguindo o padrão SINAPI se houver correspondência."
    )
    unidade: str = Field(
        description="Unidade de medida (ex: m, m2, m3, un, kg, par)."
    )
    quantidade: float = Field(
        description="Quantidade líquida extraída do DXF ou inferida pelo contexto."
    )
    preco_unitario: float = Field(
        description="Preço unitário do item. Se não encontrado na SINAPI, deve ser 0.00."
    )
    origem: str = Field(
        description="Origem do preço. Use 'sinapi' se foi encontrado na tabela fornecida, ou 'proprio' caso contrário."
    )
    justificativa: Optional[str] = Field(
        default=None,
        description="Breve explicação de por que este item foi escolhido ou como a quantidade foi calculada."
    )

class RespostaIA(BaseModel):
    """
    Schema final que a LLM deve retornar para o sistema.
    """
    itens: List[ItemOrcamento] = Field(
        description="Lista de itens de orçamento processados."
    )
    resumo: str = Field(
        description="Um resumo executivo do que foi processado neste lote de dados."
    )
    avisos: List[str] = Field(
        default_factory=list,
        description="Lista de alertas sobre divergências entre DXF e VLM, ou incertezas técnicas."
    )