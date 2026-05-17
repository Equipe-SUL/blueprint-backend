import ezdxf

doc = ezdxf.readfile("scripts_teste/4-Estrutural.dxf")
msp = doc.modelspace()

circulos_texto = 0
for e in msp:
    layer = e.dxf.layer if hasattr(e.dxf, 'layer') else '0'
    if e.dxftype() == 'CIRCLE' and layer == 'TEXTO0':
        circulos_texto += 1

print(f"Círculos na layer TEXTO0: {circulos_texto}")
