import pandas as pd


def extrair_dados_excel(caminho_ficheiro_fisico):
    try:
        df = pd.read_excel(caminho_ficheiro_fisico)
        df.columns = df.columns.str.strip().str.lower()

        soma_linhas = {}
        soma_blocos = {}

        for index, row in df.iterrows():
            conteudo = str(row.get('conteúdo', '')).strip()
            camada = str(row.get('camada', 'Sem Layer')).strip()
            tipo_cad = str(row.get('nome', 'Objeto')).strip()

            if camada == '0':
                camada = 'Rede Geral (Não Especificada)'

            geometria_inutil = ['arco', 'círculo', 'circulo', 'polilinha', 'hachura', 'dot', 'spline']
            if tipo_cad.lower() in geometria_inutil:
                continue

            layers_ignoradas = ['parede', 'cotas', 'carimbo', 'textos', 'projeção']
            if camada.lower() in layers_ignoradas:
                continue

            contagem = row.get('contagem', 1)
            if pd.isna(contagem) or str(contagem).lower() == 'nan':
                contagem = 1

            comprimento = row.get('comprimento', 0)
            if pd.isna(comprimento) or str(comprimento).lower() == 'nan':
                comprimento = 0

            if tipo_cad.lower() == 'linha' and float(comprimento) > 0:
                chave = f"Tubulação/Condutor | Layer: {camada}"
                soma_linhas[chave] = soma_linhas.get(chave, 0.0) + float(comprimento)

            elif tipo_cad.lower() in ['texto', 'textom']:
                if not conteudo or conteudo.lower() == 'nan':
                    continue
                chave = f"Texto: {conteudo} | Layer: {camada}"
                soma_blocos[chave] = soma_blocos.get(chave, 0) + int(contagem)

            else:
                nome_bloco = tipo_cad
                if conteudo and conteudo.lower() != 'nan':
                    nome_bloco = f"{tipo_cad} ({conteudo})"
                chave = f"Equipamento: {nome_bloco} | Layer: {camada}"
                soma_blocos[chave] = soma_blocos.get(chave, 0) + int(contagem)

        itens_extraidos = []

        for chave, total_metros in soma_linhas.items():
            descricao, layer = chave.split(' | Layer: ')
            itens_extraidos.append({
                "quantidade_formatada": f"{round(total_metros, 2)} metros lineares",
                "descricao": descricao,
                "layer": layer,
                "tipo_objeto": "Tubagem/Cabo"
            })

        for chave, total_unidades in soma_blocos.items():
            descricao, layer = chave.split(' | Layer: ')
            itens_extraidos.append({
                "quantidade_formatada": f"{total_unidades} unidades",
                "descricao": descricao,
                "layer": layer,
                "tipo_objeto": "Equipamento/Peça"
            })

        return {
            "sucesso": True,
            "total_linhas_agrupadas": len(itens_extraidos),
            "itens_planilhados": itens_extraidos
        }

    except Exception as e:
        return {"sucesso": False, "erro": f"Erro ao ler Excel: {str(e)}"}
