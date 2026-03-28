import ezdxf
import re
import pandas as pd
import math

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

# ---------------------------------------------------------
# NOVA FUNÇÃO PARA EXCEL
# ---------------------------------------------------------
def extrair_dados_excel(caminho_arquivo_fisico):
    try:
        df = pd.read_excel(caminho_arquivo_fisico)
        df.columns = df.columns.str.strip().str.lower()
        
        itens_extraidos = []
        
        for index, row in df.iterrows():
            conteudo = str(row.get('conteúdo', '')).strip()
            
            if not conteudo or conteudo.lower() == 'nan':
                continue
                
            contagem = row.get('contagem', 1)
            if pd.isna(contagem) or str(contagem).lower() == 'nan':  
                contagem = 1
                
            camada = str(row.get('camada', 'Sem Layer')).strip()
            tipo_cad = str(row.get('nome', 'Objeto')).strip()

            itens_extraidos.append({
                "quantidade": int(contagem),
                "descricao": conteudo,
                "layer": camada,
                "tipo_objeto": tipo_cad
            })
            
        return {
            "sucesso": True, 
            "total_linhas_uteis": len(itens_extraidos),
            "itens_planilhados": itens_extraidos
        }

    except Exception as e:
        return {"sucesso": False, "erro": f"Erro ao ler Excel: {str(e)}"}