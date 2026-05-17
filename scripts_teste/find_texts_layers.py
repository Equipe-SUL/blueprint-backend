import ezdxf
import re

doc = ezdxf.readfile("scripts_teste/4-Estrutural.dxf")
msp = doc.modelspace()

textos_p = {}
for e in msp:
    layer = e.dxf.layer if hasattr(e.dxf, 'layer') else '0'
    if e.dxftype() in ('TEXT', 'MTEXT'):
        t = e.dxf.text if e.dxftype() == 'TEXT' else e.text
        matches = re.findall(r'\bP\d+\b', t.upper())
        for m in matches:
            if m not in textos_p:
                textos_p[m] = []
            textos_p[m].append(layer)

print(f"Total Pilares Únicos pelos nomes: {len(textos_p)}")
for k in sorted(textos_p.keys(), key=lambda x: int(x[1:])):
    print(f"{k}: layers {set(textos_p[k])}")
