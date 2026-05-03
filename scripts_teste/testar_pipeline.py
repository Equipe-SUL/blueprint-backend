"""
Teste do pipeline completo usando o arquivo já salvo no projeto 21.
"""
import os
import sys
import django

caminho_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, caminho_raiz)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from apps.projetos.ai.services.pipeline_service import processar_dxf_completo

# Usa o Estrutura.dxf direto do Desktop (ou troque pelo caminho do arquivo já salvo)
CAMINHO_DXF = os.path.join(os.path.expanduser('~'), 'Desktop', 'ExtraçãoCalculo', 'Estrutura.dxf')
PROJETO_ID = 21

if __name__ == "__main__":
    print(f"Arquivo: {CAMINHO_DXF}")
    print(f"Existe: {os.path.exists(CAMINHO_DXF)}")
    print(f"Projeto ID: {PROJETO_ID}")
    print("=" * 80)

    resultado = processar_dxf_completo(CAMINHO_DXF, PROJETO_ID)

    print("\n" + "=" * 80)
    if resultado.get("sucesso"):
        print("✅ PIPELINE COMPLETO COM SUCESSO!")
        print(f"   Itens adaptados: {len(resultado.get('itens_adaptados', []))}")
        print(f"   Sugestões SINAPI: {len(resultado.get('memorial_orcamentario', []))}")
        print(f"\n   Memoriais salvos em:")
        for nome, caminho in resultado.get("caminhos", {}).items():
            print(f"     → {nome}: {caminho}")

        print("\n   ITENS ADAPTADOS (entrada do RAG):")
        for item in resultado.get("itens_adaptados", []):
            print(f"     [{item['id']}] {item['description']} → qty: {item['quantity']} {item['unidade']}")

        print("\n   SUGESTÕES SINAPI (saída do RAG):")
        for sug in resultado.get("memorial_orcamentario", []):
            print(f"\n     Item: {sug['id_cad']} ({sug['item_original']})")
            print(f"     Quantidade: {sug['quantidade']}")
            for i, op in enumerate(sug.get('opcoes_sinapi', []), 1):
                print(f"       {i}. [Cód: {op['codigo']}] {op['descricao'][:80]}...")
    else:
        print(f"❌ PIPELINE FALHOU: {resultado.get('erro')}")
