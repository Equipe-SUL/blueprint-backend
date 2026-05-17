#!/usr/bin/env python
"""
dxf_extrator_manual.py
======================
Script standalone para extração manual de dados de arquivos .dxf.
Sem Django. Sem IA. Exporta para JSON, CSV e PDF.

Uso:
    python dxf_extrator_manual.py arquivo.dxf
    python dxf_extrator_manual.py arquivo.dxf --saida ./relatorios/
    python dxf_extrator_manual.py arquivo.dxf --formato json csv pdf
"""

import argparse
import os
import sys

# Garante que o diretório raiz está no path para os imports absolutos
caminho_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if caminho_raiz not in sys.path:
    sys.path.insert(0, caminho_raiz)

from apps.projetos.ai.extracaocalculo.dxf_core import extrair_dxf
from apps.projetos.ai.extracaocalculo.dxf_exportadores import exportar_json, exportar_csv, exportar_pdf


def imprimir_resumo(memorial):
    """Imprime resumo no terminal."""
    print(f"\n{'-' * 75}")
    print(f"{'Camada':<25} {'Categoria':<12} {'Qtd':>5} {'Area (m2)':>12} "
          f"{'Perimetro':>12} {'Comp. (m)':>12} {'Volume':>10}")
    print(f"{'-' * 75}")

    for r in sorted(memorial.resumo_por_camada.values(), key=lambda x: x.camada):
        print(f"{r.camada[:24]:<25} {r.categoria:<12} {r.quantidade:>5} "
              f"{r.area_total_m2:>12.4f} {r.perimetro_total_m:>12.4f} "
              f"{r.comprimento_total_m:>12.4f} {r.volume_m3:>10.4f}")

    print(f"{'-' * 75}")

    # Totais
    area = sum(r.area_total_m2 for r in memorial.resumo_por_camada.values())
    perim = sum(r.perimetro_total_m for r in memorial.resumo_por_camada.values())
    comp = sum(r.comprimento_total_m for r in memorial.resumo_por_camada.values())
    vol = sum(r.volume_m3 for r in memorial.resumo_por_camada.values())

    print(f"\n[TOTAIS GERAIS]")
    print(f"   Entidades processadas : {memorial.total_entidades}")
    print(f"   Entidades ignoradas   : {memorial.total_ignoradas}")
    print(f"   Camadas encontradas   : {len(memorial.resumo_por_camada)}")
    print(f"   Ambientes (MTEXT)     : {len(memorial.ambientes)}")
    print(f"   Area total            : {area:.4f} m2")
    print(f"   Perimetro total       : {perim:.4f} m")
    print(f"   Comprimento total     : {comp:.4f} m")
    print(f"   Volume total          : {vol:.4f} m3")

    if memorial.ambientes:
        print(f"\n[AMBIENTES DETECTADOS]")
        for a in memorial.ambientes:
            print(f"   {a.nome}: {a.area_m2:.2f} m2 | P={a.perimetro_m:.2f} m | "
                  f"PD={a.pe_direito_m:.2f} m")


def main():
    parser = argparse.ArgumentParser(
        description="Extrator manual de dados DXF - sem IA, sem Django",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python dxf_extrator_manual.py planta.dxf
  python dxf_extrator_manual.py planta.dxf --saida ./relatorios/
  python dxf_extrator_manual.py planta.dxf --formato json csv
  python dxf_extrator_manual.py planta.dxf --formato pdf --saida ./
        """,
    )
    parser.add_argument("dxf", help="Caminho do arquivo .dxf de entrada")
    parser.add_argument(
        "--saida", "-s", default=".",
        help="Diretorio de saida (padrao: diretorio atual)",
    )
    parser.add_argument(
        "--formato", "-f", nargs="+", default=["json", "csv", "pdf"],
        choices=["json", "csv", "pdf"],
        help="Formatos de exportacao (padrao: json csv pdf)",
    )

    args = parser.parse_args()

    # Validar arquivo
    if not os.path.isfile(args.dxf):
        print(f"[ERRO] Arquivo nao encontrado: {args.dxf}")
        sys.exit(1)

    if not args.dxf.lower().endswith(".dxf"):
        print(f"[ERRO] Arquivo nao e .dxf: {args.dxf}")
        sys.exit(1)

    # Criar diretório de saída
    os.makedirs(args.saida, exist_ok=True)

    # Nome base para os arquivos de saída
    nome_base = os.path.splitext(os.path.basename(args.dxf))[0]

    # ── EXTRAIR ───────────────────────────────────────────────────────────
    memorial = extrair_dxf(args.dxf)

    # ── RESUMO NO TERMINAL ────────────────────────────────────────────────
    imprimir_resumo(memorial)

    # ── EXPORTAR ──────────────────────────────────────────────────────────
    print(f"\n[EXPORT] Exportando para: {os.path.abspath(args.saida)}")

    if "json" in args.formato:
        caminho_json = os.path.join(args.saida, f"{nome_base}_memorial.json")
        exportar_json(memorial, caminho_json)

    if "csv" in args.formato:
        caminho_csv = os.path.join(args.saida, f"{nome_base}_memorial.csv")
        exportar_csv(memorial, caminho_csv)

    if "pdf" in args.formato:
        caminho_pdf = os.path.join(args.saida, f"{nome_base}_memorial.pdf")
        exportar_pdf(memorial, caminho_pdf)

    print(f"\n[OK] Extracao completa!")


if __name__ == "__main__":
    main()
