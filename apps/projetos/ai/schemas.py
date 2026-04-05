from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Schema para saída do mapeamento de itens da LLM. a IA vai devolver uma saida JSON no formato definido aqui.

# Mantém o formato consistente com os campos essenciais do model ItemProjeto.
class ItemProjetoLLM(BaseModel):
    # Importante: a LLM pode devolver campos extras (ex.: id_item, observacoes).
    # Para evitar falhas duras de parsing, ignoramos extras e validamos apenas o núcleo.
    model_config = ConfigDict(extra='ignore')
    
    descricao: str = Field(min_length=3, max_length=400)
    codigo_sinapi: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Código SINAPI do match selecionado (obrigatório para considerar o item válido).",
    )
    unidade: str = Field(min_length=1, max_length=20, description="Ex.: m, m2, un")
    quantidade: Decimal = Field(ge=0, description="Quantidade deve ser maior ou igual a zero.")
    preco_unitario: Decimal = Field(default=Decimal('0.00'), ge=0, description="Preço unitário deve ser maior ou igual a zero.")
    # A LLM pode tentar devolver 'proprio'. Permitimos no parse para não quebrar o fluxo,
    # mas a camada de pós-processamento deve filtrar e manter apenas 'sinapi' na saída final.
    origem: Literal["sinapi", "proprio"] = "sinapi"

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
            "origem": self.origem
        }
class AvisoLLM(BaseModel):
    model_config = ConfigDict(extra='ignore')

    # Mantemos um conjunto pequeno e estável para UI/relatórios.
    # A LLM pode devolver variações (ex.: "ALERTA"); normalizamos no validator.
    nivel: str = "INFO"
    categoria: str = Field(min_length=3, max_length=80)
    mensagem: str = Field(min_length=3, max_length=1000)
    referencia: str | None = Field(
        default=None,
        max_length=400,
        description="Opcional: trecho do DXF/identificador que originou o aviso.",
    )

    @field_validator("nivel", mode="before")
    @classmethod
    def _normalizar_nivel(cls, v: Any) -> str:
        if v is None:
            return "INFO"
        valor = str(v).strip().upper()

        mapeamento = {
            "ALERTA": "ALTO",
            "WARNING": "MEDIO",
            "WARN": "MEDIO",
            "CRITICAL": "CRITICO",
            "CRITICO": "CRITICO",
            "HIGH": "ALTO",
            "MEDIUM": "MEDIO",
            "LOW": "BAIXO",
        }

        valor = mapeamento.get(valor, valor)
        permitidos = {"INFO", "BAIXO", "MEDIO", "ALTO", "CRITICO"}
        return valor if valor in permitidos else "INFO"

    @field_validator("mensagem", mode="before")
    @classmethod
    def _truncar_mensagem(cls, v: Any) -> str:
        if v is None:
            return "Aviso sem mensagem."
        texto = str(v).strip()
        if not texto:
            return "Aviso sem mensagem."
        limite = 1000
        if len(texto) <= limite:
            return texto
        sufixo = "... (truncado)"
        return texto[: max(0, limite - len(sufixo))] + sufixo


class ItensProjetoLLMSaida(BaseModel):
    model_config = ConfigDict(extra='ignore')

    itens: list[ItemProjetoLLM] = Field(
        default_factory=list,
        description=(
            "Lista de itens mapeados pela LLM. Nesta fase, somente itens com match SINAPI devem aparecer."
        ),
    )
    avisos: list[AvisoLLM] = Field(
        default_factory=list,
        description="Lista de avisos estruturados (diagnóstico/qualidade), não persiste no ItemProjeto.",
    )

    def as_payloads(self, projeto_id: int, arquivo_id:int) -> list[dict[str, Any]]:
        # Converte cada item para o formato necessário para criar um ItemProjeto via API
        return [item.as_itemprojeto_payload(projeto_id, arquivo_id) for item in self.itens]