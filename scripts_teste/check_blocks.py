import ezdxf

doc = ezdxf.readfile("scripts_teste/4-Estrutural.dxf")
msp = doc.modelspace()

blocos = {}
for e in msp:
    if e.dxftype() == 'INSERT':
        name = e.dxf.name
        blocos[name] = blocos.get(name, 0) + 1

print("Contagem de blocos inseridos:")
for n, v in blocos.items():
    print(f" - {n}: {v}")
