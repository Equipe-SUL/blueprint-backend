"""
dxf_reader.py
=============
Leitura determinística de arquivos DXF via ezdxf.

Extrai entidades do ModelSpace aplicando filtros inteligentes
(tipo de entidade + layer) e retorna dados estruturados.

**Sem IA** — toda a lógica é determinística.
"""

import ezdxf

from apps.projetos.ai.extraction.filters import (
    entidade_deve_ser_processada,
    tipo_eh_ignorado,
    TIPOS_GEOMETRICOS,
)
from apps.projetos.ai.extraction.geometry import (
    remover_z,
    arco_para_pontos,
    circulo_para_poligono,
    fechar_anel,
)


# ── Extração de geometria por tipo de entidade ──────────────────────────────

def _extrair_geometria_lwpolyline(entidade) -> dict:
    """Extrai geometria de uma LWPOLYLINE."""
    pontos = remover_z(list(entidade.get_points("xy")))
    if len(pontos) < 2:
        return None

    esta_fechada = entidade.is_closed or (len(pontos) > 2 and pontos[0] == pontos[-1])
    if esta_fechada:
        fechar_anel(pontos)

    return {
        "tipo_geometria": "Polygon" if esta_fechada else "LineString",
        "coordenadas": [pontos] if esta_fechada else pontos,
        "fechada": esta_fechada,
    }


def _extrair_geometria_polyline(entidade) -> dict:
    """Extrai geometria de uma POLYLINE."""
    pontos = remover_z(
        [(v.dxf.location.x, v.dxf.location.y) for v in entidade.vertices]
    )
    if len(pontos) < 2:
        return None

    esta_fechada = bool(entidade.dxf.flags & 1)
    if esta_fechada:
        fechar_anel(pontos)

    return {
        "tipo_geometria": "Polygon" if esta_fechada else "LineString",
        "coordenadas": [pontos] if esta_fechada else pontos,
        "fechada": esta_fechada,
    }


def _extrair_geometria_line(entidade) -> dict:
    """Extrai geometria de uma LINE."""
    pontos = [
        (float(entidade.dxf.start.x), float(entidade.dxf.start.y)),
        (float(entidade.dxf.end.x), float(entidade.dxf.end.y)),
    ]
    return {
        "tipo_geometria": "LineString",
        "coordenadas": pontos,
        "fechada": False,
    }


def _extrair_geometria_arc(entidade) -> dict:
    """Extrai geometria de um ARC (aproximado por pontos)."""
    centro = entidade.dxf.center
    pontos = arco_para_pontos(
        float(centro.x), float(centro.y),
        float(entidade.dxf.radius),
        float(entidade.dxf.start_angle),
        float(entidade.dxf.end_angle),
    )
    return {
        "tipo_geometria": "LineString",
        "coordenadas": pontos,
        "fechada": False,
        "raio": float(entidade.dxf.radius),
    }


def _extrair_geometria_circle(entidade) -> dict:
    """Extrai geometria de um CIRCLE (aproximado por polígono)."""
    centro = entidade.dxf.center
    pontos = circulo_para_poligono(float(centro.x), float(centro.y), float(entidade.dxf.radius))
    return {
        "tipo_geometria": "Polygon",
        "coordenadas": [pontos],
        "fechada": True,
        "raio": float(entidade.dxf.radius),
    }


def _extrair_geometria_spline(entidade) -> dict:
    """Extrai geometria de uma SPLINE (pontos de controle)."""
    pontos = remover_z([(p[0], p[1]) for p in entidade.control_points])
    if len(pontos) < 2:
        return None

    return {
        "tipo_geometria": "LineString",
        "coordenadas": pontos,
        "fechada": False,
    }


def _extrair_geometria_ellipse(entidade) -> dict:
    """Extrai geometria de uma ELLIPSE (aproximada por pontos)."""
    try:
        # ezdxf pode gerar pontos de flattening para elipses
        pontos = remover_z(list(entidade.flattening(0.01)))
        if len(pontos) < 3:
            return None
        fechar_anel(pontos)
        return {
            "tipo_geometria": "Polygon",
            "coordenadas": [pontos],
            "fechada": True,
        }
    except Exception:
        return None


# ── Mapeamento de extratores ────────────────────────────────────────────────

_EXTRATORES = {
    "LWPOLYLINE": _extrair_geometria_lwpolyline,
    "POLYLINE": _extrair_geometria_polyline,
    "LINE": _extrair_geometria_line,
    "ARC": _extrair_geometria_arc,
    "CIRCLE": _extrair_geometria_circle,
    "SPLINE": _extrair_geometria_spline,
    "ELLIPSE": _extrair_geometria_ellipse,
}


# ── Função principal de leitura ─────────────────────────────────────────────

def ler_entidades_dxf(caminho_dxf: str) -> dict:
    """
    Lê um arquivo DXF e retorna entidades estruturadas com filtros aplicados.

    Retorna:
        dict com:
          - entidades_brutas: lista de entidades extraídas
          - layers_encontradas: lista de layers únicas
          - estatisticas_extracao: contagem por tipo de entidade
          - total_ignorados: quantas entidades foram filtradas
          - motivos_ignorados: contagem por motivo de exclusão
    """
    print(f"\n📂 [EXTRAÇÃO] Lendo arquivo DXF: {caminho_dxf}")

    doc = ezdxf.readfile(caminho_dxf)
    msp = doc.modelspace()

    entidades = []
    layers = set()
    stats = {}
    total_ignorados = 0
    motivos_ignorados = {}

    for e in msp:
        tipo = e.dxftype()
        layer = e.dxf.layer
        stats[tipo] = stats.get(tipo, 0) + 1
        layers.add(layer)

        # Aplica filtros inteligentes
        if not entidade_deve_ser_processada(tipo, layer):
            total_ignorados += 1
            motivo = f"tipo:{tipo}" if tipo_eh_ignorado(tipo) else f"layer:{layer}"
            motivos_ignorados[motivo] = motivos_ignorados.get(motivo, 0) + 1
            continue

        # Extrai geometria
        extrator = _EXTRATORES.get(tipo)
        if extrator is None:
            total_ignorados += 1
            motivos_ignorados[f"sem_extrator:{tipo}"] = (
                motivos_ignorados.get(f"sem_extrator:{tipo}", 0) + 1
            )
            continue

        try:
            geometria = extrator(e)
            if geometria is None:
                total_ignorados += 1
                motivos_ignorados["geometria_invalida"] = (
                    motivos_ignorados.get("geometria_invalida", 0) + 1
                )
                continue
        except Exception as erro:
            print(f"  ⚠️  Erro ao extrair {tipo} (layer={layer}): {erro}")
            total_ignorados += 1
            motivos_ignorados["erro_extracao"] = (
                motivos_ignorados.get("erro_extracao", 0) + 1
            )
            continue

        entidades.append({
            "tipo": tipo,
            "layer": layer,
            "handle": e.dxf.handle,
            "geometria": geometria,
        })

    # Relatório
    print(f"   ✅ Entidades extraídas: {len(entidades)}")
    print(f"   🚫 Entidades ignoradas: {total_ignorados}")
    print(f"   📋 Layers encontradas: {sorted(layers)}")

    if motivos_ignorados:
        print("   📊 Motivos de exclusão:")
        for motivo, qtd in sorted(motivos_ignorados.items(), key=lambda x: -x[1]):
            print(f"      {motivo}: {qtd}")

    return {
        "entidades_brutas": entidades,
        "layers_encontradas": sorted(layers),
        "estatisticas_extracao": stats,
        "total_ignorados": total_ignorados,
        "motivos_ignorados": motivos_ignorados,
    }
