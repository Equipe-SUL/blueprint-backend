"""
dxf_exportadores.py
===================
Exportadores de MemorialCalculo para JSON, CSV e PDF.
"""

import csv
import json
import os
from dataclasses import asdict
from typing import List

from fpdf import FPDF

from .dxf_core import MemorialCalculo, ResumoCamada


# ── JSON ──────────────────────────────────────────────────────────────────────

def exportar_json(memorial: MemorialCalculo, caminho: str) -> str:
    """Exporta o memorial completo como JSON estruturado."""
    dados = {
        "arquivo_origem": memorial.arquivo_origem,
        "total_entidades": memorial.total_entidades,
        "total_ignoradas": memorial.total_ignoradas,
        "ambientes": [asdict(a) for a in memorial.ambientes],
        "textos_legenda": memorial.textos_legenda,
        "resumo_por_camada": {
            k: asdict(v) for k, v in memorial.resumo_por_camada.items()
        },
        "resumo_geral": _resumo_geral(memorial),
        "entidades": [
            {
                "indice": e.indice,
                "tipo_entidade": e.tipo_entidade,
                "camada": e.camada,
                "categoria": e.categoria,
                "fechada": e.fechada,
                "comprimento_m": e.comprimento_m,
                "area_m2": e.area_m2,
                "perimetro_m": e.perimetro_m,
            }
            for e in memorial.entidades
        ],
    }

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    print(f"[SALVO] JSON: {caminho}")
    return caminho


# ── CSV ───────────────────────────────────────────────────────────────────────

def exportar_csv(memorial: MemorialCalculo, caminho: str) -> str:
    """Exporta resumo por camada como CSV flat."""
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "Camada", "Categoria", "Quantidade",
            "Área Total (m²)", "Perímetro Total (m)",
            "Comprimento Total (m)", "Volume (m³)",
            "Área Líquida (m²)",
        ])
        for r in sorted(memorial.resumo_por_camada.values(), key=lambda x: x.camada):
            writer.writerow([
                r.camada, r.categoria, r.quantidade,
                f"{r.area_total_m2:.4f}",
                f"{r.perimetro_total_m:.4f}",
                f"{r.comprimento_total_m:.4f}",
                f"{r.volume_m3:.4f}",
                f"{r.area_liquida_m2:.4f}",
            ])

        # Linha de totais
        rg = _resumo_geral(memorial)
        writer.writerow([])
        writer.writerow([
            "TOTAL", "", rg["total_entidades"],
            f"{rg['area_total_m2']:.4f}",
            f"{rg['perimetro_total_m']:.4f}",
            f"{rg['comprimento_total_m']:.4f}",
            f"{rg['volume_total_m3']:.4f}",
            "",
        ])

        # Ambientes
        if memorial.ambientes:
            writer.writerow([])
            writer.writerow(["AMBIENTES (extraídos de textos MTEXT)"])
            writer.writerow(["Nome", "Área (m²)", "Perímetro (m)", "Pé-direito (m)"])
            for a in memorial.ambientes:
                writer.writerow([a.nome, f"{a.area_m2:.2f}", f"{a.perimetro_m:.2f}", f"{a.pe_direito_m:.2f}"])

    print(f"[SALVO] CSV: {caminho}")
    return caminho


# ── PDF ───────────────────────────────────────────────────────────────────────

class RelatorioPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Memorial de Calculo - Extracao DXF", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", align="C")


def exportar_pdf(memorial: MemorialCalculo, caminho: str) -> str:
    """Exporta o memorial como PDF com tabelas formatadas."""
    pdf = RelatorioPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    nome_arquivo = os.path.basename(memorial.arquivo_origem)

    # Info do arquivo
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Arquivo: {nome_arquivo}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Entidades processadas: {memorial.total_entidades} | "
             f"Ignoradas: {memorial.total_ignoradas}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Camadas encontradas: {len(memorial.resumo_por_camada)} | "
             f"Ambientes: {len(memorial.ambientes)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Tabela: Resumo por camada
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Resumo por Camada", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Cabeçalho da tabela
    col_w = [45, 25, 15, 28, 28, 28, 22]
    headers = ["Camada", "Categoria", "Qtd", "Area (m2)", "Perimetro (m)", "Comprimento (m)", "Volume (m3)"]

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(40, 40, 60)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()

    # Linhas
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    fill = False
    for r in sorted(memorial.resumo_por_camada.values(), key=lambda x: x.camada):
        if fill:
            pdf.set_fill_color(235, 235, 245)
        else:
            pdf.set_fill_color(255, 255, 255)

        nome_camada = r.camada[:20] if len(r.camada) > 20 else r.camada
        pdf.cell(col_w[0], 6, nome_camada, border=1, fill=True)
        pdf.cell(col_w[1], 6, r.categoria, border=1, fill=True, align="C")
        pdf.cell(col_w[2], 6, str(r.quantidade), border=1, fill=True, align="C")
        pdf.cell(col_w[3], 6, f"{r.area_total_m2:.2f}", border=1, fill=True, align="R")
        pdf.cell(col_w[4], 6, f"{r.perimetro_total_m:.2f}", border=1, fill=True, align="R")
        pdf.cell(col_w[5], 6, f"{r.comprimento_total_m:.2f}", border=1, fill=True, align="R")
        pdf.cell(col_w[6], 6, f"{r.volume_m3:.2f}", border=1, fill=True, align="R")
        pdf.ln()
        fill = not fill

    # Totais
    rg = _resumo_geral(memorial)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(40, 40, 60)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(col_w[0], 7, "TOTAL", border=1, fill=True)
    pdf.cell(col_w[1], 7, "", border=1, fill=True)
    pdf.cell(col_w[2], 7, str(rg["total_entidades"]), border=1, fill=True, align="C")
    pdf.cell(col_w[3], 7, f"{rg['area_total_m2']:.2f}", border=1, fill=True, align="R")
    pdf.cell(col_w[4], 7, f"{rg['perimetro_total_m']:.2f}", border=1, fill=True, align="R")
    pdf.cell(col_w[5], 7, f"{rg['comprimento_total_m']:.2f}", border=1, fill=True, align="R")
    pdf.cell(col_w[6], 7, f"{rg['volume_total_m3']:.2f}", border=1, fill=True, align="R")
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)

    # Tabela: Ambientes
    if memorial.ambientes:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Ambientes (extraidos de textos MTEXT)", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        amb_w = [60, 35, 40, 35]
        amb_h = ["Nome", "Area (m2)", "Perimetro (m)", "Pe-direito (m)"]

        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(40, 40, 60)
        pdf.set_text_color(255, 255, 255)
        for i, h in enumerate(amb_h):
            pdf.cell(amb_w[i], 7, h, border=1, fill=True, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(0, 0, 0)
        for a in memorial.ambientes:
            pdf.cell(amb_w[0], 6, a.nome[:30], border=1)
            pdf.cell(amb_w[1], 6, f"{a.area_m2:.2f}", border=1, align="R")
            pdf.cell(amb_w[2], 6, f"{a.perimetro_m:.2f}", border=1, align="R")
            pdf.cell(amb_w[3], 6, f"{a.pe_direito_m:.2f}", border=1, align="R")
            pdf.ln()

    pdf.output(caminho)
    print(f"[SALVO] PDF: {caminho}")
    return caminho


# ── Utilidades ────────────────────────────────────────────────────────────────

def _resumo_geral(memorial: MemorialCalculo) -> dict:
    area = sum(r.area_total_m2 for r in memorial.resumo_por_camada.values())
    perim = sum(r.perimetro_total_m for r in memorial.resumo_por_camada.values())
    comp = sum(r.comprimento_total_m for r in memorial.resumo_por_camada.values())
    vol = sum(r.volume_m3 for r in memorial.resumo_por_camada.values())
    return {
        "total_entidades": memorial.total_entidades,
        "total_ignoradas": memorial.total_ignoradas,
        "area_total_m2": round(area, 4),
        "perimetro_total_m": round(perim, 4),
        "comprimento_total_m": round(comp, 4),
        "volume_total_m3": round(vol, 4),
        "total_ambientes": len(memorial.ambientes),
        "total_camadas": len(memorial.resumo_por_camada),
    }
