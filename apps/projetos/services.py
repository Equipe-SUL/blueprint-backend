import ezdxf
import re
import pandas as pd
import math
import base64
import requests
import json
import os

# =====================================================================
# INÍCIO DO BLOCO DXF (PLANO A)
# =====================================================================
def parse_ambiente(texto_bruto):
    if 'm²' in texto_bruto and 'P=' in texto_bruto:
        linhas = texto_bruto.split('\\P')
        try:
            nome = re.sub(r'\\[a-zA-Z0-9.]+;', '', linhas[0]).strip()
            area = re.search(r'([\d,]+)m²', linhas[1]).group(1)
            perimetro = re.search(r'P=([\d,]+)m', linhas[2]).group(1)
            pe_direito = "0"
            if len(linhas) > 3 and 'PD=' in linhas[3]:
                pe_direito = re.search(r'PD=([\d,]+)', linhas[3]).group(1)
            return {"nome": nome, "area_m2": area, "perimetro_m": perimetro, "pe_direito_m": pe_direito}
        except Exception:
            return None
    return None

def extrair_dados_dxf(caminho_arquivo_fisico):
    try:
        doc = ezdxf.readfile(caminho_arquivo_fisico)
        msp = doc.modelspace()
        
        ambientes = []
        textos_descritivos = []
        contagem_tags = {} 
        
        for entity in msp.query('TEXT MTEXT'):
            texto_sujo = entity.dxf.text
            dados_ambiente = parse_ambiente(texto_sujo)
            
            if dados_ambiente:
                ambientes.append(dados_ambiente)
            else:
                texto_limpo = texto_sujo.replace('\\P', ' ')
                texto_limpo = re.sub(r'\\[a-zA-Z0-9.]+;', '', texto_limpo).strip()
                
                if not texto_limpo:
                    continue
                    
                if len(texto_limpo) > 2:
                    textos_descritivos.append({
                        "texto": texto_limpo,
                        "layer": entity.dxf.layer
                    })
                else:
                    chave = f"Etiqueta '{texto_limpo}' | Layer: {entity.dxf.layer}"
                    contagem_tags[chave] = contagem_tags.get(chave, 0) + 1

        lista_quantidades = [
            {"identificador": k, "quantidade": v} 
            for k, v in contagem_tags.items()
        ]

        return {
            "sucesso": True, 
            "itens": {
                "ambientes": ambientes,
                "textos_legenda": textos_descritivos,
                "quantidades_por_etiqueta": lista_quantidades
            }
        }

    except Exception as e:
        return {"sucesso": False, "erro": str(e)}


# =====================================================================
# INÍCIO DO BLOCO EXCEL (PLANO B) 
# =====================================================================
def extrair_dados_excel(caminho_ficheiro_fisico):
    try:
        df = pd.read_excel(caminho_ficheiro_fisico)
        df.columns = df.columns.str.strip().str.lower()
        
        # Dicionários para somar os valores agrupados
        soma_linhas = {} # Para somar os comprimentos (metros lineares)
        soma_blocos = {} # Para somar as contagens (unidades)
        
        for index, row in df.iterrows():
            conteudo = str(row.get('conteúdo', '')).strip()
            camada = str(row.get('camada', 'Sem Layer')).strip()
            tipo_cad = str(row.get('nome', 'Objeto')).strip() # NOME DO BLOCO!
            
            # TRADUTOR DE LAYER 0 (Mantido)
            if camada == '0':
                camada = 'Rede Geral (Não Especificada)'

            # LIXO GEOMÉTRICO: Coisas que o CAD exporta mas não são materiais reais
            geometria_inutil = ['arco', 'círculo', 'circulo', 'polilinha', 'hachura', 'dot', 'spline']
            if tipo_cad.lower() in geometria_inutil:
                continue # O Python deita isso fora e nem olha pra trás
                
            layers_ignoradas = ['parede', 'cotas', 'carimbo', 'textos', 'projeção']
            if camada.lower() in layers_ignoradas:
                continue 
            
            contagem = row.get('contagem', 1)
            if pd.isna(contagem) or str(contagem).lower() == 'nan':  
                contagem = 1
                
            comprimento = row.get('comprimento', 0)
            if pd.isna(comprimento) or str(comprimento).lower() == 'nan':
                comprimento = 0
            
            # 1. Se for Tubulação (Linha)
            if tipo_cad.lower() == 'linha' and float(comprimento) > 0:
                chave = f"Tubulação/Condutor | Layer: {camada}"
                soma_linhas[chave] = soma_linhas.get(chave, 0.0) + float(comprimento)
                
            # 2. Se for Texto Puro (ex: "AF DN 50")
            elif tipo_cad.lower() in ['texto', 'textom']:
                if not conteudo or conteudo.lower() == 'nan':
                    continue # Se for texto vazio, pula
                chave = f"Texto: {conteudo} | Layer: {camada}"
                soma_blocos[chave] = soma_blocos.get(chave, 0) + int(contagem)
                
            # 3. SE FOR BLOCO (Pias, Vasos, Registros, etc!)
            else:
                # Usa o Nome do Bloco (tipo_cad) como descrição principal!
                nome_bloco = tipo_cad
                # Se por acaso o bloco tiver um texto de atributo, junta os dois
                if conteudo and conteudo.lower() != 'nan':
                    nome_bloco = f"{tipo_cad} ({conteudo})"
                    
                chave = f"Equipamento: {nome_bloco} | Layer: {camada}"
                soma_blocos[chave] = soma_blocos.get(chave, 0) + int(contagem)

        # Montar a lista final mastigada para a IA
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


def montar_prompt_dinamico(disciplina):
    """
    Injeta os alvos corretos dependendo se é Hidráulica, Elétrica, etc.
    """
    alvos_por_disciplina = {
        "hidrossanitario": [
            "Caixas de passagem, inspeção ou gordura",
            "Vasos sanitários",
            "Pias / Bancadas",
            "Ralos secos ou sifonados",
            "Lavatórios",
            "Caixas d'água"
        ],
        "eletrica": [
            "Quadros de Distribuição",
            "Luminárias",
            "Tomadas e Interruptores"
        ]
    }

    # Pega os alvos da disciplina ou um genérico
    itens_alvo = alvos_por_disciplina.get(disciplina.lower(), ["Equipamentos principais"])
    lista_formatada = "\n    - ".join(itens_alvo)

    prompt = f"""
    Você é um engenheiro inspetor avaliando uma planta baixa da disciplina: {disciplina.upper()}.
    Aja com extrema precisão visual. Não invente ou alucine dados.
    Localize e conte a quantidade dos seguintes itens na planta:

    ATENÇÃO - REGRA RÍGIDA: Analise APENAS a vista principal de 'PLANTA BAIXA'. 
    IGNORE completamente os desenhos 'ISOMÉTRICOS', 'DETALHES' e 'ESQUEMAS' nas laterais da prancha para não contar a mesma peça duas vezes.
    
    - {lista_formatada}
    
    Retorne o resultado ESTRITAMENTE no formato JSON válido, onde as chaves são os nomes dos itens e os valores são números inteiros.
    Exemplo de saída: {{"Vasos sanitários": 3, "Ralos": 4}}
    NÃO escreva nenhum texto fora do JSON.
    """
    return prompt

def analisar_imagem_com_vlm(caminho_imagem, disciplina="hidrossanitario"):
    """
    Envia a imagem da planta para o MiniCPM-V local no Ollama.
    """
    if not os.path.exists(caminho_imagem):
        return {"sucesso": False, "erro": "Arquivo de imagem não encontrado."}

    # 1. Converte a imagem para Base64
    try:
        with open(caminho_imagem, "rb") as image_file:
            imagem_b64 = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        return {"sucesso": False, "erro": f"Erro ao processar imagem: {str(e)}"}

    # 2. Monta o prompt dinâmico
    prompt = montar_prompt_dinamico(disciplina)

    # 3. Payload para a API do Ollama
    payload = {
        "model": "minicpm-v",
        "prompt": prompt,
        "images": [imagem_b64],
        "format": "json", # Força a saída estruturada
        "stream": False,
        "options": {
            "temperature": 0.0 # Temperatura ZERO para máxima precisão e zero criatividade
        }
    }

    try:
        # A porta padrão do Ollama é 11434
        url_ollama = "http://localhost:11434/api/generate"
        
        # Faz a requisição (pode demorar dependendo da sua placa de vídeo)
        resposta = requests.post(url_ollama, json=payload, timeout=120)
        resposta.raise_for_status()
        
        dados_ia = resposta.json()
        
        # O Ollama devolve a resposta dentro da chave "response"
        resultado_texto = dados_ia.get("response", "{}")
        
        # Limpa possível formatação markdown (```json ... ```) que a IA teima em colocar
        resultado_texto = resultado_texto.replace("```json", "").replace("```", "").strip()
        
        resultado_json = json.loads(resultado_texto)
        
        return {
            "sucesso": True,
            "inspecao_visual": resultado_json
        }
        
    except requests.exceptions.RequestException as e:
        return {"sucesso": False, "erro": f"Ollama não respondeu. Ele está rodando? Erro: {str(e)}"}
    except json.JSONDecodeError:
        return {"sucesso": False, "erro": f"A IA não retornou um JSON válido. Retorno bruto: {resultado_texto}"}
    except Exception as e:
        return {"sucesso": False, "erro": f"Erro inesperado: {str(e)}"}