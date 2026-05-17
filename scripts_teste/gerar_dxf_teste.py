"""
Gera um DXF de teste com entidades estruturais para validar o extrator.
"""
import ezdxf

doc = ezdxf.new("R2010")
msp = doc.modelspace()

# Criar layers
doc.layers.add("PILAR", color=1)
doc.layers.add("VIGA", color=2)
doc.layers.add("LAJE", color=3)
doc.layers.add("PAREDE", color=4)
doc.layers.add("ESQUADRIAS", color=5)
doc.layers.add("ARQ - TEXTOS", color=7)
doc.layers.add("COTAS", color=8)

# ── PILARES (polígonos fechados) ──
# Pilar 1: 0.20 x 0.40 m
msp.add_lwpolyline(
    [(0, 0), (0.20, 0), (0.20, 0.40), (0, 0.40), (0, 0)],
    dxfattribs={"layer": "PILAR"},
    close=True,
)
# Pilar 2
msp.add_lwpolyline(
    [(5, 0), (5.20, 0), (5.20, 0.40), (5, 0.40), (5, 0)],
    dxfattribs={"layer": "PILAR"},
    close=True,
)
# Pilar 3
msp.add_lwpolyline(
    [(0, 5), (0.30, 5), (0.30, 5.30), (0, 5.30), (0, 5)],
    dxfattribs={"layer": "PILAR"},
    close=True,
)

# ── VIGAS (linhas) ──
msp.add_line((0.10, 0.20), (5.10, 0.20), dxfattribs={"layer": "VIGA"})
msp.add_line((0.10, 5.15), (5.10, 5.15), dxfattribs={"layer": "VIGA"})

# ── LAJE (polígono grande fechado) ──
msp.add_lwpolyline(
    [(0, 0), (10, 0), (10, 8), (0, 8), (0, 0)],
    dxfattribs={"layer": "LAJE"},
    close=True,
)

# ── PAREDES ──
msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "PAREDE"})  # 10m
msp.add_line((10, 0), (10, 8), dxfattribs={"layer": "PAREDE"})  # 8m
msp.add_line((10, 8), (0, 8), dxfattribs={"layer": "PAREDE"})   # 10m
msp.add_line((0, 8), (0, 0), dxfattribs={"layer": "PAREDE"})    # 8m

# ── ESQUADRIAS (vãos) ──
msp.add_line((2, 0), (3.2, 0), dxfattribs={"layer": "ESQUADRIAS"})  # porta 1.2m
msp.add_line((6, 0), (8, 0), dxfattribs={"layer": "ESQUADRIAS"})    # janela 2m

# ── TEXTOS (ambiente MTEXT com formatação) ──
msp.add_mtext(
    "Sala\\P12,50m²\\PP=15,00m\\PPD=2,80",
    dxfattribs={"layer": "ARQ - TEXTOS", "insert": (3, 4)},
)
msp.add_mtext(
    "Quarto\\P9,80m²\\PP=12,60m\\PPD=2,80",
    dxfattribs={"layer": "ARQ - TEXTOS", "insert": (7, 4)},
)

# ── COTAS (devem ser ignoradas) ──
msp.add_line((0, -0.5), (10, -0.5), dxfattribs={"layer": "COTAS"})
msp.add_text("10.00", dxfattribs={"layer": "COTAS", "insert": (5, -0.8)})

# ── CIRCLE (pilar circular - estaca) ──
msp.add_circle((2.5, 2.5), radius=0.15, dxfattribs={"layer": "PILAR"})

# Salvar
caminho = "teste_estrutura.dxf"
doc.saveas(caminho)
print(f"[OK] DXF de teste gerado: {caminho}")
