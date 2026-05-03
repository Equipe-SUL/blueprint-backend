"""
dxf_para_geojson.py
====================
Converte arquivos .dxf em .geojson, suportando os principais tipos de entidade:
  - LWPOLYLINE  → Polígono (se fechada) ou LineString
  - POLYLINE    → Polígono (se fechada) ou LineString
  - LINE        → LineString
  - ARC         → LineString (aproximado por pontos)
  - CIRCLE      → Polígono (aproximado por pontos)
  - SPLINE      → LineString (pontos de controle)

Uso:
    python dxf_para_geojson.py arquivo.dxf
    python dxf_para_geojson.py arquivo.dxf --camada "LOTES"
    python dxf_para_geojson.py arquivo.dxf --saida resultado.geojson
"""

import sys
import json
import math
import argparse
import ezdxf

# ── Funções auxiliares ────────────────────────────────────────────────────────


def arco_para_pontos(cx, cy, raio, angulo_inicio_graus, angulo_fim_graus, segmentos=64):
    """Aproxima um arco por uma lista de pontos (x, y)."""
    inicio = math.radians(angulo_inicio_graus)
    fim = math.radians(angulo_fim_graus)
    if fim < inicio:
        fim += 2 * math.pi
    angulos = [inicio + (fim - inicio) * i / segmentos for i in range(segmentos + 1)]
    return [(cx + raio * math.cos(a), cy + raio * math.sin(a)) for a in angulos]


def circulo_para_poligono(cx, cy, raio, segmentos=64):
    """Aproxima um círculo por um polígono fechado."""
    pontos = arco_para_pontos(cx, cy, raio, 0, 360, segmentos)
    pontos.append(pontos[0])  # fecha o anel
    return pontos


def fechar_anel(coords):
    """Garante que o primeiro e o último ponto sejam iguais (anel fechado)."""
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def apenas_2d(pontos):
    """Remove a coordenada Z, mantendo apenas (x, y)."""
    return [(p[0], p[1]) for p in pontos]


# ── Conversores por tipo de entidade ─────────────────────────────────────────


def lwpolyline_para_feature(entidade, filtro_camada):
    """Converte uma entidade LWPOLYLINE para Feature GeoJSON."""
    if filtro_camada and entidade.dxf.layer != filtro_camada:
        return None

    pontos = apenas_2d(list(entidade.get_points("xy")))
    if len(pontos) < 2:
        return None

    esta_fechada = entidade.is_closed or (len(pontos) > 2 and pontos[0] == pontos[-1])

    if esta_fechada:
        fechar_anel(pontos)
        geometria = {"type": "Polygon", "coordinates": [pontos]}
    else:
        geometria = {"type": "LineString", "coordinates": pontos}

    return {
        "type": "Feature",
        "geometry": geometria,
        "properties": {
            "Layer": entidade.dxf.layer,
            "SubClasses": "AcDbPolyline",
            "EntityHandle": entidade.dxf.handle,
            "tipo_entidade": "LWPOLYLINE",
            "fechada": esta_fechada,
        },
    }


def polyline_para_feature(entidade, filtro_camada):
    """Converte uma entidade POLYLINE para Feature GeoJSON."""
    if filtro_camada and entidade.dxf.layer != filtro_camada:
        return None

    pontos = apenas_2d(
        [(v.dxf.location.x, v.dxf.location.y) for v in entidade.vertices]
    )
    if len(pontos) < 2:
        return None

    esta_fechada = bool(entidade.dxf.flags & 1)

    if esta_fechada:
        fechar_anel(pontos)
        geometria = {"type": "Polygon", "coordinates": [pontos]}
    else:
        geometria = {"type": "LineString", "coordinates": pontos}

    return {
        "type": "Feature",
        "geometry": geometria,
        "properties": {
            "Layer": entidade.dxf.layer,
            "SubClasses": "AcDbPolyline",
            "EntityHandle": entidade.dxf.handle,
            "tipo_entidade": "POLYLINE",
            "fechada": esta_fechada,
        },
    }


def linha_para_feature(entidade, filtro_camada):
    """Converte uma entidade LINE para Feature GeoJSON."""
    if filtro_camada and entidade.dxf.layer != filtro_camada:
        return None

    pontos = [
        (entidade.dxf.start.x, entidade.dxf.start.y),
        (entidade.dxf.end.x, entidade.dxf.end.y),
    ]
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": pontos},
        "properties": {
            "Layer": entidade.dxf.layer,
            "SubClasses": "AcDbLine",
            "EntityHandle": entidade.dxf.handle,
            "tipo_entidade": "LINE",
        },
    }


def arco_para_feature(entidade, filtro_camada):
    """Converte uma entidade ARC para Feature GeoJSON (aproximado por pontos)."""
    if filtro_camada and entidade.dxf.layer != filtro_camada:
        return None

    centro = entidade.dxf.center
    pontos = arco_para_pontos(
        centro.x,
        centro.y,
        entidade.dxf.radius,
        entidade.dxf.start_angle,
        entidade.dxf.end_angle,
    )
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": pontos},
        "properties": {
            "Layer": entidade.dxf.layer,
            "SubClasses": "AcDbArc",
            "EntityHandle": entidade.dxf.handle,
            "tipo_entidade": "ARC",
            "raio": entidade.dxf.radius,
        },
    }


def circulo_para_feature(entidade, filtro_camada):
    """Converte uma entidade CIRCLE para Feature GeoJSON (aproximado por polígono)."""
    if filtro_camada and entidade.dxf.layer != filtro_camada:
        return None

    centro = entidade.dxf.center
    pontos = circulo_para_poligono(centro.x, centro.y, entidade.dxf.radius)
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [pontos]},
        "properties": {
            "Layer": entidade.dxf.layer,
            "SubClasses": "AcDbCircle",
            "EntityHandle": entidade.dxf.handle,
            "tipo_entidade": "CIRCLE",
            "raio": entidade.dxf.radius,
        },
    }


def spline_para_feature(entidade, filtro_camada):
    """Converte uma entidade SPLINE para Feature GeoJSON (pontos de controle)."""
    if filtro_camada and entidade.dxf.layer != filtro_camada:
        return None

    pontos = apenas_2d([(p[0], p[1]) for p in entidade.control_points])
    if len(pontos) < 2:
        return None

    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": pontos},
        "properties": {
            "Layer": entidade.dxf.layer,
            "SubClasses": "AcDbSpline",
            "EntityHandle": entidade.dxf.handle,
            "tipo_entidade": "SPLINE",
        },
    }


# ── Mapeamento de tipos para funções conversoras ──────────────────────────────

CONVERSORES = {
    "LWPOLYLINE": lwpolyline_para_feature,
    "POLYLINE": polyline_para_feature,
    "LINE": linha_para_feature,
    "ARC": arco_para_feature,
    "CIRCLE": circulo_para_feature,
    "SPLINE": spline_para_feature,
}


# ── Função principal ──────────────────────────────────────────────────────────


def dxf_para_geojson(
    caminho_dxf: str, caminho_saida: str = None, filtro_camada: str = None
):
    """
    Lê um arquivo DXF e exporta um GeoJSON com todas as geometrias encontradas.

    Parâmetros:
        caminho_dxf    : caminho do arquivo .dxf de entrada
        caminho_saida  : caminho do arquivo .geojson de saída (opcional)
        filtro_camada  : nome da camada (layer) a filtrar (opcional)
    """
    print(f"\n📂 Lendo arquivo: {caminho_dxf}")

    doc = ezdxf.readfile(caminho_dxf)
    espaco_modelo = doc.modelspace()

    features = []
    total_ignorados = 0
    contagem_tipos = {}

    for entidade in espaco_modelo:
        tipo = entidade.dxftype()
        conversor = CONVERSORES.get(tipo)

        # Tipo não suportado: apenas contabiliza e segue
        if conversor is None:
            total_ignorados += 1
            contagem_tipos[tipo] = contagem_tipos.get(tipo, 0) + 1
            continue

        try:
            feature = conversor(entidade, filtro_camada)
            if feature:
                features.append(feature)
            contagem_tipos[tipo] = contagem_tipos.get(tipo, 0) + 1
        except Exception as erro:
            print(
                f"  ⚠️  Erro ao processar {tipo} (camada={entidade.dxf.layer}): {erro}"
            )
            total_ignorados += 1

    # Monta o objeto GeoJSON final
    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    # Define o caminho de saída, se não informado
    if caminho_saida is None:
        caminho_saida = caminho_dxf.rsplit(".", 1)[0] + ".geojson"

    with open(caminho_saida, "w", encoding="utf-8") as arquivo:
        json.dump(geojson, arquivo, ensure_ascii=False, indent=2)

    # Exibe o relatório final
    print(f"\n✅ GeoJSON gerado com sucesso: {caminho_saida}")
    print(f"   Features exportadas : {len(features)}")
    print(f"   Entidades ignoradas : {total_ignorados}")
    print("\n   Resumo por tipo de entidade:")
    for tipo, quantidade in sorted(contagem_tipos.items()):
        suporte = "✔ suportado" if tipo in CONVERSORES else "✘ não suportado"
        print(f"     {tipo:20s} {quantidade:>5}  ({suporte})")

    return caminho_saida


# ── Interface de linha de comando ─────────────────────────────────────────────


def main():
    analisador = argparse.ArgumentParser(
        description="Converte um arquivo .dxf em .geojson"
    )
    analisador.add_argument(
        "dxf",
        help="Caminho do arquivo .dxf de entrada",
    )
    analisador.add_argument(
        "--saida",
        "-s",
        help="Caminho do arquivo .geojson de saída (padrão: mesmo nome do .dxf)",
    )
    analisador.add_argument(
        "--camada",
        "-c",
        help="Filtrar apenas uma camada (layer) específica do DXF",
    )

    args = analisador.parse_args()
    dxf_para_geojson(args.dxf, args.saida, args.camada)


if __name__ == "__main__":
    main()
