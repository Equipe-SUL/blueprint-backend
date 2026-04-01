from __future__ import annotations 

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Schema para saída do mapeamento de itens da LLM. a IA vai devolver uma saida JSON no formato definido aqui.

# Mantém o formato consistente com os campos essenciais do model ItemProjeto.
class ItemProjetoLLM(BaseModel):
    model_config = ConfigDict(extra='forbid') # Proibe campos extras, garantindo que a LLM envie o que foi definido aqui.
    
    descricao: str = Field(min_length=3, max_length=400)
    unidade: str = Field(min_length=1, max_length=20, description="Ex.: m, m2, un")
    quantidade: Decimal = Field(gt=0, description="Quantidade deve ser maior que zero.")
    preco_unitario: Decimal = Field(default=Decimal('0.00'), ge=0, description="Preço unitário deve ser maior ou igual a zero.")

    # Campo opicional para uma explicação rápida da escolha (não vai pro bd)
    justificativa: str | None = Field(default=None, max_length=300)

    def as_itemprojeto_payload(self, projeto_id: int, arquivo_id: int) -> dict[str, Any]:
        # Payload necessario para criar um ItemProjeto via API
        return {
            "projeto": projeto_id,
            "arquivo": arquivo_id,
            "descricao": self.descricao,
            "unidade": self.unidade,
            "quantidade": self.quantidade,
            "preco_unitario": self.preco_unitario,
        }
    
class ItensProjetoLLMSaida(BaseModel):
    model_config = ConfigDict(extra='forbid') # Proibe campos extras, garantindo que a LLM envie o que foi definido aqui.

    itens: list[ItemProjetoLLM] = Field(default_factory=list, description="Lista de itens mapeados pela LLM. Deve conter pelo menos um item.")
    avisos: list[str] = Field(default_factory=list, description="Lista de avisos ou mensagens da LLM, como incertezas ou sugestões para o usuário.")

    def as_payloads(self, projeto_id: int, arquivo_id:int) -> list[dict[str, Any]]:
        # Converte cada item para o formato necessário para criar um ItemProjeto via API
        return [item.as_itemprojeto_payload(projeto_id, arquivo_id) for item in self.itens]