import os
import django
import json

# 1. Liga o motor do Django para podermos usar o banco de dados e as configurações
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

# 2. Agora sim importamos a nossa IA
from apps.projetos.ai.interpretation import interpretar_itens_extraidos_dxf

# 3. Os dados falsos para simular o DXF
dxf_falso = {
    "textos_legenda": [
        {"texto": "15 Tubo PVC Esgoto 100mm", "layer": "HIDRO_TUBULACAO"},
        {"texto": "10 un Caixa de inspecao em alvenaria", "layer": "HIDRO_CAIXAS"},
        {"texto": "Tijolo de vidro decorativo 20x20", "layer": "ARQ_DETALHES"}
    ],
    "ambientes": ["Área Externa", "Banheiro"],
    "quantidades_por_etiqueta": {}
}

# 4. Execução principal
if __name__ == "__main__":
    print("\n🚀 Iniciando a simulação RAG + LLM...\n")
    
    resultado = interpretar_itens_extraidos_dxf(
        itens_extraidos=dxf_falso, 
        tipo_projeto=["Hidrossanitário e Arquitetura"]
    )

    print("\n✅ === RESULTADO FINAL DA IA === ✅")
    print(json.dumps(resultado.model_dump(), indent=2, ensure_ascii=False))