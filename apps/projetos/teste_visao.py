from services import analisar_imagem_com_vlm

print("Enviando imagem para o MiniCPM-V... Aguarde (pode demorar uns segundos).")

# Coloque o nome da sua imagem aqui
resultado = analisar_imagem_com_vlm("hidrossanitario4_pages-to-jpg-0001.jpg", disciplina="hidrossanitario")

if resultado["sucesso"]:
    print("\n✅ SUCESSO! A VLM encontrou o seguinte:")
    import json
    print(json.dumps(resultado["inspecao_visual"], indent=4, ensure_ascii=False))
else:
    print(f"\n❌ ERRO: {resultado['erro']}")