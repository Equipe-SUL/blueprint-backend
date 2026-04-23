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



   