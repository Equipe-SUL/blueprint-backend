import os
import django
import json

# 1. Configuração do ambiente Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings') # Ajuste se seu projeto tiver outro nome
django.setup()

from apps.projetos.models import Projeto, ArquivoUpload, ItemProjeto
from apps.projetos.ai.orchestrator import processar_planta_completa

def rodar_teste_real():
    print("🚀 Iniciando Teste Integrado (VLM + RAG + Banco de Dados)")

    # 2. Criar um Projeto de teste no Banco de Dados
    # Isso simula o usuário criando uma obra no seu sistema
    projeto_db, _ = Projeto.objects.get_or_create(
        nome_obra="Obra Teste Caçapava",
        cidade_obra="Caçapava",
        estado_obra="SP",
        tipo_projeto=["hidraulica"] # Define a disciplina para o RAG e VLM
    )

    # 3. Criar um registro de ArquivoUpload
    # Substitua 'planta_teste.jpg' pelo nome real do seu arquivo na pasta
    caminho_imagem = os.path.abspath("planta_teste.jpg")
    
    if not os.path.exists(caminho_imagem):
        print(f"❌ Erro: O arquivo {caminho_imagem} não foi encontrado!")
        return

    arquivo_db, _ = ArquivoUpload.objects.get_or_create(
        projeto=projeto_db,
        nome_original=caminho_imagem,
        caminho_arquivo=caminho_imagem,
        status_processamento="pendente"
    )

    # 4. Simular os dados que viriam do extrator de DXF
    json_dxf_fake = {
        "textos_legenda": [
            {"texto": "5 Tubo PVC Esgoto 100mm", "layer": "HIDRO_TUBULACAO"},
            {"texto": "2 Caixa de inspecao", "layer": "HIDRO_CAIXAS"}
        ],
        "ambientes": ["Banheiro Social"],
        "quantidades_por_etiqueta": {}
    }

    # 5. EXECUTAR O ORQUESTRADOR
    print("\n--- 🧠 Chamando o Orquestrador ---")
    resultado = processar_planta_completa(
        caminho_imagem="planta_teste.jpg",
        json_dxf=json_dxf_fake,
        tipo_projeto=["Hidrossanitário e Arquitetura"], 
        alvos_visao=["Vasos sanitários", "Pias", "Ralos"]
    )

    # 6. Verificação dos Resultados (Acessando como Objeto Pydantic)
    if resultado.itens or resultado.resumo:
        print("\n✅ TESTE CONCLUÍDO COM SUCESSO!")
        print(f"Resumo da IA: {resultado.resumo}")
        print(f"Total de itens processados: {len(resultado.itens)}")
        
        print("\n--- 📊 ITENS GERADOS PELA IA ---")
        for item in resultado.itens:
            # Como item também é um objeto Pydantic (ItemOrcamento), usamos ponto!
            print(f"- {item.descricao} | Qtd: {item.quantidade} | Preço: R${item.preco_unitario} | Origem: {item.origem}")
            if item.justificativa:
                print(f"  └ Justificativa: {item.justificativa}")
        
        if resultado.avisos:
            print("\n--- ⚠️ AVISOS DA IA ---")
            for aviso in resultado.avisos:
                print(f" - {aviso}")

        # Observação: Para salvar no banco de verdade, você faria um loop aqui:
        # for item in resultado.itens:
        #     ItemProjeto.objects.create(arquivo=arquivo_db, descricao=item.descricao, ...)
    else:
        print(f"\n❌ O teste não retornou itens.")

if __name__ == "__main__":
    rodar_teste_real()