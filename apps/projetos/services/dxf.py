from core.engine import process_dxf
from core.exporters.geojson import to_geojson


def extrair_dados_dxf(caminho_arquivo_fisico):
    try:
        result = process_dxf(caminho_arquivo_fisico)
        if not result.success:
            return {"sucesso": False, "erro": result.error or "Engine geométrica falhou"}

        ambientes_geometricos = []
        adjacencia = {}

        if result.metrics:
            for i, room in enumerate(result.metrics.rooms):
                nome = "Ambiente"
                if i < len(result.rooms):
                    nome = result.rooms[i].get("nome_sugerido", f"Ambiente {i + 1}")
                ambientes_geometricos.append({
                    "nome": nome,
                    "area_m2": str(room.area_m2),
                    "perimetro_m": str(room.perimeter_m),
                    "centroid": {"x": room.centroid_x, "y": room.centroid_y},
                })

            if result.metrics.adjacency:
                for idx, vizinhos in result.metrics.adjacency.items():
                    adjacencia[str(idx)] = vizinhos

        textos_descritivos = []
        contagem_tags = {}
        for t in result.texts:
            texto = t.get("texto", "")
            if not texto:
                continue
            if len(texto) > 2:
                textos_descritivos.append({
                    "texto": texto,
                    "layer": t.get("layer", ""),
                })
            else:
                chave = f"Etiqueta '{texto}' | Layer: {t.get('layer', '')}"
                contagem_tags[chave] = contagem_tags.get(chave, 0) + 1

        lista_quantidades = [
            {"identificador": k, "quantidade": v}
            for k, v in contagem_tags.items()
        ]

        return {
            "sucesso": True,
            "itens": {
                "ambientes": ambientes_geometricos,
                "textos_legenda": textos_descritivos,
                "quantidades_por_etiqueta": lista_quantidades,
                "geometria": {
                    "segmentos": result.stats.get("segmentos_brutos", 0),
                    "topologia_vertices": result.stats.get("vertices_grafo", 0),
                    "topologia_arestas": result.stats.get("arestas_grafo", 0),
                    "poligonos_encontrados": result.stats.get("poligonos", 0),
                    "area_total_calculada_m2": result.stats.get("area_total_m2", 0),
                    "perimetro_total_calculado_m": result.stats.get("perimetro_total_m", 0),
                },
                "diagnostico": {
                    "dangles": result.stats.get("dangles", 0),
                    "cuts": result.stats.get("cuts", 0),
                    "invalid_rings": result.stats.get("invalid_rings", 0),
                },
                "adjacencia": adjacencia,
                "unidades": {
                    "nome": result.ir.unit_name if result.ir else "Meters",
                    "escala_para_metros": result.ir.unit_scale if result.ir else 1.0,
                },
                "parser_errors": result.ir.errors if result.ir and result.ir.errors else [],
                "geojson": to_geojson(result),
            },
        }

    except Exception as e:
        return {"sucesso": False, "erro": str(e)}
