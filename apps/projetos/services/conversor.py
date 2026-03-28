import math
import ezdxf
from ezdxf import path

def converter_dxf_para_lista_itens(caminho_arquivo, arquivo_id):
    try:
        doc = ezdxf.readfile(caminho_arquivo)
        msp = doc.modelspace()
        lista_itens = []

        for entity in msp:
            layer = entity.dxf.layer.upper()
            if layer in ['0', 'DEFPOINTS']: continue

            quantidade = 0
            unidade = "un"

            # MÉTODO ROBUSTO: Tenta converter a entidade em um "path" para medir o comprimento
            if entity.dxftype() in ['LINE', 'LWPOLYLINE', 'POLYLINE', 'ARC', 'CIRCLE']:
                try:
                    # Transforma a entidade em um caminho geométrico e mede o comprimento real
                    entity_path = path.make_path(entity)
                    quantidade = path.length(entity_path)
                    unidade = "m"
                except:
                    # Fallback caso o path falhe (ex: círculos em versões antigas)
                    if entity.dxftype() == 'LINE':
                        quantidade = math.dist(entity.dxf.start, entity.dxf.end)
                    elif entity.dxftype() == 'CIRCLE':
                        quantidade = 1.0 # Ou 2 * math.pi * entity.dxf.radius se quiser o perímetro
                        unidade = "un"
            
            elif entity.dxftype() == 'INSERT': # Blocos (ex: tomadas, luminárias)
                quantidade = 1.0
                unidade = "un"

            if quantidade > 0:
                lista_itens.append({
                    "arquivo": arquivo_id,
                    "descricao": f"Material: {layer} (Ref: {entity.dxf.handle})",
                    "unidade": unidade,
                    "quantidade": f"{quantidade:.2f}",
                    "preco_unitario": "0.00"
                })
        return lista_itens
    except Exception as e:
        raise Exception(f"Erro na conversão DXF: {str(e)}")