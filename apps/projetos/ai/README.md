# AI (LangChain/Ollama/RAG)

Esta pasta é o “núcleo de IA” do app `projetos`.

Arquivos sugeridos:
- `config.py`: lê variáveis do `.env` (ex.: `OLLAMA_BASE_URL`, modelo, timeouts)
- `client.py`: cliente/LLM wrapper (LangChain + Ollama)
- `schemas.py`: schemas de saída (ex.: JSON dos itens no shape do `ItemProjeto`)
- `interpretation.py`: DXF extraído -> itens interpretados (LLM)
- `retrieval.py`: recuperação (RAG) para SINAPI (top-k, rerank etc.)
- `embeddings.py`: geração/atualização de embeddings (indexação)
- `prompts.py`: prompts para serem utilizados
