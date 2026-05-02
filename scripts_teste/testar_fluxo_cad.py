import os
import sys
import django

# Força o Python a olhar para a raiz do projeto primeiro
caminho_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, caminho_raiz)

# Configura o Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

# IMPORTAÇÃO CORRIGIDA: Usa a função nova que busca as Top 5 sugestões
from apps.projetos.ai.services.orcamento_service import gerar_sugestoes_orcamento

# O JSON MULTIDISCIPLINAR DO CAD
json_exemplo_cad = [
    {
        "id": "beam_001",
        "type": "viga",
        "volume_m3": 1.51,
        "description": "Viga de concreto armado 12x30 cm"
    },
    {
        "id": "wall_001",
        "type": "parede",
        "quantity": 45.0, # m2
        "description": "Alvenaria de vedação de blocos cerâmicos furados 9x19x19cm"
    },
    {
        "id": "pipe_001",
        "type": "tubulacao",
        "quantity": 12.0, # metros
        "description": "Tubo de PVC soldável de 40mm para água fria"
    }
]

def rodar_teste_fluxo():
    print("=== TESTE DE FLUXO GLOBAL: CAD -> RAG (Top 5 Opções) ===")
    
    # Chama o serviço atualizado
    resultado = gerar_sugestoes_orcamento(json_exemplo_cad)
    
    print("\n" + "="*80)
    print("RESULTADO DO RAG (TOP 5 OPÇÕES PARA A INTERFACE DO USUÁRIO):")
    print("="*80)
    
    for res in resultado:
        print(f"\nItem CAD: {res['id_cad']} ({res['item_original']})")
        print(f"Quantidade/Volume extraído: {res['quantidade']}")
        print("Opções SINAPI sugeridas pela IA:")
        
        # O serviço agora devolve uma lista de dicionários, vamos imprimi-los
        for i, opcao in enumerate(res['opcoes_sinapi'], 1):
            print(f"  {i}. [Cód: {opcao['codigo']}] {opcao['descricao']}")
            
        print("-" * 80)

if __name__ == "__main__":
    rodar_teste_fluxo()