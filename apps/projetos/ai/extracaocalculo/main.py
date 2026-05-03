"""
calculos_geojson.py
====================
Calcula área e perímetro das geometrias contidas em um arquivo .geojson
gerado a partir de um DXF (ex: via QGIS ou conversores similares).

Estrutura esperada das propriedades:
    "Layer"       → nome da camada (ex: "PILAR", "ESTACA", "VIGA")
    "SubClasses"  → tipo interno do AutoCAD (ex: "AcDbPolyline")
    "EntityHandle"→ identificador único da entidade

Regras de interpretação:
    - Coordenadas podem ter Z → é removido automaticamente
    - LineString fechada (1º == último ponto) → tratada como Polígono
    - Point → ignorado nos cálculos (cotas e textos)
    - MultiLineString → cada parte calculada separadamente

Uso:
    python calculos_geojson.py arquivo.geojson
    python calculos_geojson.py arquivo.geojson --camada "PILAR"
    python calculos_geojson.py arquivo.geojson --saida relatorio.json
"""

import json
import math
import argparse


# ── Funções auxiliares ────────────────────────────────────────────────────────


def remover_z(coords):
    """Remove a coordenada Z de uma lista de pontos, mantendo apenas (x, y)."""
    return [(p[0], p[1]) for p in coords]


def esta_fechada(coords):
    """
    Verifica se uma sequência de coordenadas forma um anel fechado,
    ou seja, se o primeiro e o último ponto são iguais (ou muito próximos).
    """
    if len(coords) < 3:
        return False
    dx = abs(coords[0][0] - coords[-1][0])
    dy = abs(coords[0][1] - coords[-1][1])
    return dx < 1e-9 and dy < 1e-9


def calcular_area(anel):
    """
    Calcula a área de um anel usando a fórmula de Gauss (Shoelace).
    Retorna a área em unidades do sistema de coordenadas.
    """
    n = len(anel)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += anel[i][0] * anel[j][1]
        area -= anel[j][0] * anel[i][1]
    return abs(area) / 2.0


def calcular_perimetro(coords):
    """
    Calcula o perímetro de um anel ou o comprimento de uma linha,
    somando a distância euclidiana entre pontos consecutivos.
    """
    total = 0.0
    for i in range(len(coords) - 1):
        dx = coords[i + 1][0] - coords[i][0]
        dy = coords[i + 1][1] - coords[i][1]
        total += math.sqrt(dx**2 + dy**2)
    return total


# ── Processadores por tipo de geometria ───────────────────────────────────────


def processar_linestring(coords_brutas, propriedades):
    """
    Processa uma LineString.
    Se estiver fechada → calcula área e perímetro (polígono implícito).
    Se estiver aberta  → calcula apenas comprimento.
    """
    coords = remover_z(coords_brutas)

    if esta_fechada(coords):
        area = calcular_area(coords)
        perimetro = calcular_perimetro(coords)
        return {
            "interpretacao": "Polígono (LineString fechada)",
            "area_m2": round(area, 4),
            "perimetro_m": round(perimetro, 4),
        }
    else:
        comprimento = calcular_perimetro(coords)
        return {
            "interpretacao": "Linha aberta",
            "comprimento_m": round(comprimento, 4),
        }


def processar_polygon(aneis_brutos, propriedades):
    """
    Processa um Polygon GeoJSON.
    Primeiro anel = contorno externo; demais = buracos (subtraídos da área).
    """
    anel_externo = remover_z(aneis_brutos[0])
    area = calcular_area(anel_externo)
    perimetro = calcular_perimetro(anel_externo)

    for buraco in aneis_brutos[1:]:
        area -= calcular_area(remover_z(buraco))

    return {
        "interpretacao": "Polígono",
        "area_m2": round(area, 4),
        "perimetro_m": round(perimetro, 4),
    }


def processar_multilinestring(lista_coords, propriedades):
    """
    Processa um MultiLineString, calculando cada parte individualmente.
    """
    partes = []
    area_total = 0.0
    perimetro_total = 0.0
    comprimento_total = 0.0

    for i, coords_brutas in enumerate(lista_coords):
        parte = processar_linestring(coords_brutas, propriedades)
        parte["parte"] = i + 1
        partes.append(parte)
        area_total += parte.get("area_m2", 0)
        perimetro_total += parte.get("perimetro_m", 0)
        comprimento_total += parte.get("comprimento_m", 0)

    return {
        "interpretacao": "MultiLineString",
        "area_total_m2": round(area_total, 4),
        "perimetro_total_m": round(perimetro_total, 4),
        "comprimento_total_m": round(comprimento_total, 4),
        "partes": partes,
    }


# ── Dispatcher ────────────────────────────────────────────────────────────────

PROCESSADORES = {
    "LineString": processar_linestring,
    "Polygon": processar_polygon,
    "MultiLineString": processar_multilinestring,
    # "Point" é ignorado intencionalmente (textos, cotas, pontos de referência)
}


# ── Função principal ──────────────────────────────────────────────────────────


def calcular_geojson(
    caminho_geojson: str, filtro_camada: str = None, caminho_saida: str = None
):
    """
    Lê um GeoJSON e calcula área/perímetro de cada feature.

    Parâmetros:
        caminho_geojson : caminho do arquivo .geojson de entrada
        filtro_camada   : filtrar apenas uma camada específica (opcional)
        caminho_saida   : salvar relatório em .json (opcional)
    """
    print(f"\n📂 Lendo arquivo: {caminho_geojson}")

    with open(caminho_geojson, "r", encoding="utf-8") as arq:
        geojson = json.load(arq)

    features = geojson.get("features", [])
    resultados = []

    # Acumuladores globais
    area_total_geral = 0.0
    perimetro_total_geral = 0.0
    comprimento_total = 0.0
    ignorados = 0

    print(f"\n{'─' * 70}")
    print(f"{'Nº':>4}  {'Camada':<16}  {'SubClasse':<22}  {'Resultado'}")
    print(f"{'─' * 70}")

    for indice, feature in enumerate(features, start=1):
        geometria = feature.get("geometry") or {}
        propriedades = feature.get("properties") or {}

        # Lê o nome da camada com "Layer" (maiúsculo) — padrão do arquivo
        camada = propriedades.get("Layer", "—")
        subclasse = propriedades.get("SubClasses", "—")
        handle = propriedades.get("EntityHandle", "—")
        tipo_geo = geometria.get("type", "")
        coords = geometria.get("coordinates", [])

        # Aplica filtro de camada, se informado
        if filtro_camada and camada != filtro_camada:
            continue

        # Ignora pontos (textos, cotas, pontos de referência)
        if tipo_geo == "Point":
            ignorados += 1
            continue

        processador = PROCESSADORES.get(tipo_geo)

        if processador is None:
            ignorados += 1
            print(
                f"{indice:>4}  {camada:<16}  {subclasse:<22}  ⚠️ tipo '{tipo_geo}' não suportado"
            )
            continue

        try:
            calculo = processador(coords, propriedades)
        except Exception as erro:
            ignorados += 1
            print(f"{indice:>4}  {camada:<16}  {subclasse:<22}  ❌ erro: {erro}")
            continue

        # Regra específica para não contar detalhes abertos como se fossem pilares/estacas
        if (
            camada in ["PILAR", "ESTACA"]
            and calculo.get("interpretacao") == "Linha aberta"
        ):
            ignorados += 1
            continue

        # Monta o resultado completo
        calculo.update(
            {
                "indice": indice,
                "camada": camada,
                "subclasse": subclasse,
                "handle": handle,
            }
        )
        resultados.append(calculo)

        # Acumula totais globais
        area_total_geral += calculo.get("area_m2", 0) or calculo.get("area_total_m2", 0)
        perimetro_total_geral += calculo.get("perimetro_m", 0) or calculo.get(
            "perimetro_total_m", 0
        )
        comprimento_total += calculo.get("comprimento_m", 0) or calculo.get(
            "comprimento_total_m", 0
        )

        # Exibe linha de resultado no terminal
        interp = calculo.get("interpretacao", tipo_geo)
        if "area_m2" in calculo:
            linha = (
                f"Área={calculo['area_m2']:.4f} m²  "
                f"Perímetro={calculo['perimetro_m']:.4f} m  [{interp}]"
            )
        elif "area_total_m2" in calculo:
            linha = (
                f"Área={calculo['area_total_m2']:.4f} m²  "
                f"Perímetro={calculo['perimetro_total_m']:.4f} m  [{interp}]"
            )
        else:
            linha = f"Comprimento={calculo.get('comprimento_m', 0):.4f} m  [{interp}]"

        print(f"{indice:>4}  {camada:<16}  {subclasse:<22}  {linha}")

    # ── Resumo por camada ─────────────────────────────────────────────────────
    resumo_camadas = {}
    for r in resultados:
        cam = r["camada"]
        if cam not in resumo_camadas:
            resumo_camadas[cam] = {
                "quantidade": 0,
                "area_m2": 0.0,
                "perimetro_m": 0.0,
                "comprimento_m": 0.0,
            }
        resumo_camadas[cam]["quantidade"] += 1
        resumo_camadas[cam]["area_m2"] += r.get("area_m2", 0) or r.get(
            "area_total_m2", 0
        )
        resumo_camadas[cam]["perimetro_m"] += r.get("perimetro_m", 0) or r.get(
            "perimetro_total_m", 0
        )
        resumo_camadas[cam]["comprimento_m"] += r.get("comprimento_m", 0) or r.get(
            "comprimento_total_m", 0
        )

    print(f"\n{'─' * 70}")
    print(f"\n📊 RESUMO POR CAMADA")
    print(
        f"  {'Camada':<16}  {'Qtd':>5}  {'Área (m²)':>12}  {'Perímetro (m)':>14}  {'Comp. (m)':>10}"
    )
    print(f"  {'─' * 16}  {'─' * 5}  {'─' * 12}  {'─' * 14}  {'─' * 10}")
    for cam, dados in sorted(resumo_camadas.items()):
        print(
            f"  {cam:<16}  {dados['quantidade']:>5}  "
            f"{dados['area_m2']:>12.4f}  "
            f"{dados['perimetro_m']:>14.4f}  "
            f"{dados['comprimento_m']:>10.4f}"
        )

    print(f"\n📊 TOTAIS GERAIS")
    print(f"   Features processadas  : {len(resultados)}")
    print(f"   Ignoradas (Point etc) : {ignorados}")
    print(f"   Área total            : {area_total_geral:.4f} m²")
    print(f"   Área total            : {area_total_geral / 10000:.6f} ha")
    print(f"   Perímetro total       : {perimetro_total_geral:.4f} m")
    print(f"   Comprimento total     : {comprimento_total:.4f} m")

    # ── Salva relatório em JSON ───────────────────────────────────────────────
    relatorio = {
        "arquivo_origem": caminho_geojson,
        "filtro_camada": filtro_camada,
        "resumo_geral": {
            "total_features": len(resultados),
            "ignoradas": ignorados,
            "area_total_m2": round(area_total_geral, 4),
            "area_total_ha": round(area_total_geral / 10000, 6),
            "perimetro_total_m": round(perimetro_total_geral, 4),
            "comprimento_total_m": round(comprimento_total, 4),
        },
        "resumo_por_camada": {
            cam: {
                k: round(v, 4) if isinstance(v, float) else v for k, v in dados.items()
            }
            for cam, dados in resumo_camadas.items()
        },
        "features": resultados,
    }

    if caminho_saida:
        with open(caminho_saida, "w", encoding="utf-8") as arq:
            json.dump(relatorio, arq, ensure_ascii=False, indent=2)
        print(f"\n💾 Relatório salvo em: {caminho_saida}")

    return relatorio


# ── Interface de linha de comando ─────────────────────────────────────────────


def main():
    analisador = argparse.ArgumentParser(
        description="Calcula área e perímetro de geometrias em um arquivo .geojson"
    )
    analisador.add_argument(
        "geojson",
        help="Caminho do arquivo .geojson de entrada",
    )
    analisador.add_argument(
        "--camada",
        "-c",
        help="Filtrar apenas uma camada específica (ex: PILAR, ESTACA, VIGA)",
    )
    analisador.add_argument(
        "--saida",
        "-s",
        help="Salvar relatório completo em um arquivo .json",
    )

    args = analisador.parse_args()
    calcular_geojson(args.geojson, args.camada, args.saida)


if __name__ == "__main__":
    main()
