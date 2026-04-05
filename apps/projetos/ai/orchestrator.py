import os
from typing import Any, Dict, List
from django.db import transaction

# Importação dos seus Models
from apps.projetos.models import Projeto, ArquivoUpload, ItemProjeto

# Importação das peças de I.A. que construímos
from .vision import analisar_imagem_com_vlm
from .interpretation import interpretar_itens_extraidos_dxf

def processar_projeto_completo(arquivo_id: int, json_dxf: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orquestra o fluxo completo:
    1. Recupera dados do Banco (Django Models)
    2. Executa a VLM (Visão Computacional) com persona de especialista
    3. Executa a LLM + RAG (Interpretação e Preços SINAPI)
    4. Salva os resultados no banco de dados (ItemProjeto)
    """
    
    try:
        # 1. Busca os dados do arquivo e do projeto no banco de dados
        # Usamos select_related para buscar o projeto junto em uma única consulta
        arquivo = ArquivoUpload.objects.select_related('projeto').get(id=arquivo_id)
        projeto = arquivo.projeto
        
        # Como tipo_projeto é um ArrayField, pegamos a disciplina principal
        # Se estiver vazio, usamos 'alvenaria' como padrão seguro
        disciplina_principal = projeto.tipo_projeto[0] if projeto.tipo_projeto else "alvenaria"
        
        print(f"\n[Orquestrador]  Iniciando processamento de: {arquivo.nome_original}")
        print(f"[Orquestrador]  Disciplina detectada: {disciplina_principal}")

        # 2. Passo 1: VLM (Visão)
        # Definimos alvos genéricos baseados na disciplina para a VLM procurar
        alvos_padrao = ["tubulações", "caixas de passagem", "quadros", "fiação"] if disciplina_principal in ['eletrica', 'hidraulica'] else ["paredes", "vãos", "pilares"]
        
        print("[Orquestrador] 👁️ Chamando VLM para análise visual...")
        resultado_vlm = analisar_imagem_com_vlm(
            caminho_imagem=arquivo.caminho_arquivo, # Certifique-se que o caminho está correto
            alvos=alvos_padrao,
            disciplina=disciplina_principal
        )

        contexto_visual = "Nenhuma análise visual disponível."
        if resultado_vlm.get("sucesso"):
            contexto_visual = resultado_vlm.get("dados")
            print(f"[Orquestrador]  Visão concluída com sucesso.")
        else:
            print(f"[Orquestrador] ⚠️ Aviso: VLM falhou, seguindo apenas com dados do DXF. Erro: {resultado_vlm.get('erro')}")

        # 3. Passo 2: RAG + LLM (Interpretação)
        # Injetamos o relatório da visão dentro do dicionário do DXF
        json_dxf["analise_visual"] = contexto_visual

        print("[Orquestrador] 🧠 Chamando Interpretação (RAG + Qwen)...")
        resposta_ia = interpretar_itens_extraidos_dxf(
            itens_extraidos=json_dxf,
            tipo_projeto=[disciplina_principal]
        )

        # 4. Passo 3: Persistência no Banco de Dados (Salvar Itens)
        # Usamos transaction.atomic para garantir que ou salva tudo ou nada
        print(f"[Orquestrador] 💾 Salvando {len(resposta_ia.itens)} itens no banco de dados...")
        
        with transaction.atomic():
            itens_criados = []
            for item in resposta_ia.itens:
                novo_item = ItemProjeto(
                    projeto=projeto,
                    arquivo=arquivo,
                    descricao=item.descricao,
                    unidade=item.unidade,
                    quantidade=item.quantidade,
                    preco_unitario=item.preco_unitario,
                    origem=item.origem, # 'sinapi' ou 'proprio'
                    status_mapeamento='processado'
                )
                itens_criados.append(novo_item)
            
            # Bulk create é muito mais rápido que salvar um por um
            ItemProjeto.objects.bulk_create(itens_criados)

            # Atualiza o status do arquivo para processado
            arquivo.status_processamento = ArquivoUpload.Status.PROCESSADO
            arquivo.save()

        print("[Orquestrador]  Fluxo finalizado com sucesso!")
        
        return {
            "status": "sucesso",
            "itens_processados": len(itens_criados),
            "avisos": resposta_ia.avisos
        }

    except ArquivoUpload.DoesNotExist:
        return {"status": "erro", "mensagem": "Arquivo não encontrado no banco de dados."}
    except Exception as e:
        print(f" Erro crítico no Orquestrador: {str(e)}")
        # Se der erro, tentamos marcar o arquivo com erro no banco
        try:
            arquivo = ArquivoUpload.objects.get(id=arquivo_id)
            arquivo.status_processamento = ArquivoUpload.Status.ERRO
            arquivo.save()
        except:
            pass
        return {"status": "erro", "mensagem": str(e)}