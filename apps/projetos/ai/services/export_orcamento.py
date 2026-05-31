"""
export_orcamento.py
===================
Exporta resultados de orcamento SINAPI para CSV e PDF.
"""
import os
from datetime import datetime
from typing import List, Dict, Optional

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def fmt_moeda(valor: float) -> str:
    """Formata como R$ 1.234,56 — string, pra evitar dependência de locale do Excel."""
    if valor is None:
        return "R$ 0,00"
    s = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def exportar_csv(
    sugestoes: List[Dict],
    orcamento: Dict,
    output_path: str,
    metadados: Optional[Dict] = None,
) -> str:
    """
    Exporta planilha de orcamento para .xlsx formatado (Excel).

    Args:
        sugestoes: Saida do gerar_sugestoes_orcamento()
        orcamento: Saida do calcular_orcamento_final()
        output_path: Caminho para salvar o .xlsx
        metadados: Metadados da obra (opcional) para cabecalho

    Returns:
        Caminho do arquivo gerado
    """
    if not output_path.endswith(".xlsx"):
        output_path = output_path.rsplit(".", 1)[0] + ".xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "Orcamento SINAPI"

    nome_obra = (metadados or {}).get("nome", "")
    local = (metadados or {}).get("localizacao", "")

    # ── Estilos ─────────────────────────────────────────────────────────
    bold = Font(bold=True, size=11)
    bold_white = Font(bold=True, size=11, color="FFFFFF")
    title_font = Font(bold=True, size=14)
    header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    resumo_fill = PatternFill(start_color="D5F5E3", end_color="D5F5E3", fill_type="solid")
    bdi_fill = PatternFill(start_color="F2F4F4", end_color="F2F4F4", fill_type="solid")
    total_fill = PatternFill(start_color="A9DFBF", end_color="A9DFBF", fill_type="solid")
    sem_match_fill = PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    qty_fmt = '0,00'

    # ── Cabeçalho ───────────────────────────────────────────────────────
    r = 1
    ws.cell(r, 1, f"ORÇAMENTO SINAPI - {nome_obra}").font = title_font
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
    r += 1
    if local:
        ws.cell(r, 1, f"Local: {local}").font = bold
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
        r += 1
    ws.cell(r, 1, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}").font = Font(size=10, italic=True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
    r += 2

    resumo = orcamento.get("resumo", {})

    subtotal = float(resumo.get("subtotal", 0))
    valor_bdi = float(resumo.get("valor_bdi", 0))
    total_geral = float(resumo.get("total_geral", 0))
    taxa_bdi = float(resumo.get("taxa_bdi_percentual", 0))

    # ── Resumo Financeiro ──────────────────────────────────────────────
    ws.cell(r, 1, "RESUMO FINANCEIRO").font = Font(bold=True, size=12, color="2C3E50")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    r += 1

    resumo_header = ["", "DESCRIÇÃO", "", "", "", "", "VALOR", ""]
    for c, h in enumerate(resumo_header, 1):
        if h:
            cell = ws.cell(r, c, h)
            cell.font = bold_white
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
        else:
            ws.cell(r, c).border = thin_border
    r += 1

    for label, valor, fill in [
        ("Subtotal", subtotal, resumo_fill),
        (f"BDI ({taxa_bdi:.1f}%)", valor_bdi, bdi_fill),
    ]:
        ws.cell(r, 1).border = thin_border
        ws.cell(r, 2, label).font = bold
        ws.cell(r, 2).fill = fill
        ws.cell(r, 2).border = thin_border
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        cell_v = ws.cell(r, 7, fmt_moeda(valor))
        cell_v.font = bold
        cell_v.fill = fill
        cell_v.border = thin_border
        cell_v.alignment = Alignment(horizontal="right")
        ws.merge_cells(start_row=r, start_column=7, end_row=r, end_column=8)
        ws.cell(r, 8).border = thin_border
        r += 1

    ws.cell(r, 1).border = thin_border
    ws.cell(r, 2, "TOTAL GERAL").font = Font(bold=True, size=12, color="1E8449")
    ws.cell(r, 2).fill = total_fill
    ws.cell(r, 2).border = thin_border
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    cell_t = ws.cell(r, 7, fmt_moeda(total_geral))
    cell_t.font = Font(bold=True, size=12, color="1E8449")
    cell_t.fill = total_fill
    cell_t.border = thin_border
    cell_t.alignment = Alignment(horizontal="right")
    ws.merge_cells(start_row=r, start_column=7, end_row=r, end_column=8)
    ws.cell(r, 8).border = thin_border
    r += 2

    # ── Tabela de Itens ────────────────────────────────────────────────
    ws.cell(r, 1, "ITENS DO ORÇAMENTO").font = Font(bold=True, size=12, color="2C3E50")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
    r += 1

    headers = [
        "ITEM", "TIPO", "DESCRIÇÃO", "QTD", "UN",
        "CÓDIGO SINAPI", "DESCRIÇÃO SINAPI",
        "PREÇO UNIT.", "TOTAL", "STATUS",
    ]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(r, c, h)
        cell.font = bold_white
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    r += 1

    for s in sugestoes:
        id_cad = s.get("id_cad", "")
        item_original = s.get("item_original", "")
        quantidade = float(s.get("quantidade", 0))
        unidade = s.get("unidade", "un")
        tipo = s.get("tipo", "desconhecido")
        auto = s.get("selecao_automatica")
        opcoes = s.get("opcoes_sinapi", [])

        ws.cell(r, 1, id_cad).border = thin_border
        ws.cell(r, 2, tipo).border = thin_border
        ws.cell(r, 3, item_original[:80]).border = thin_border
        cell_qtd = ws.cell(r, 4, quantidade)
        cell_qtd.number_format = qty_fmt
        cell_qtd.border = thin_border
        ws.cell(r, 5, unidade).border = thin_border

        if auto is not None and auto < len(opcoes):
            escolha = opcoes[auto]
            preco = float(escolha.get("preco_unitario", 0))
            total = quantidade * preco
            desc = escolha.get("descricao", "").split("| Descrição: ")[-1][:120]

            ws.cell(r, 6, escolha.get("codigo", "")).border = thin_border
            ws.cell(r, 7, desc).border = thin_border

            ws.cell(r, 8, fmt_moeda(preco)).border = thin_border
            ws.cell(r, 8).alignment = Alignment(horizontal="right")
            ws.cell(r, 9, fmt_moeda(total)).border = thin_border
            ws.cell(r, 9).alignment = Alignment(horizontal="right")

            ws.cell(r, 10, "OK").font = Font(color="27AE60", bold=True)
            ws.cell(r, 10).border = thin_border
            ws.cell(r, 10).alignment = Alignment(horizontal="center")
        else:
            ws.merge_cells(start_row=r, start_column=6, end_row=r, end_column=7)
            ws.cell(r, 6, "---").border = thin_border
            ws.cell(r, 7).border = thin_border
            ws.cell(r, 8, "---").border = thin_border
            ws.cell(r, 9, "---").border = thin_border
            ws.cell(r, 10, "SEM MATCH").font = Font(color="C0392B", bold=True)
            ws.cell(r, 10).border = thin_border
            ws.cell(r, 10).alignment = Alignment(horizontal="center")
        r += 1

    # ── Itens sem matching ─────────────────────────────────────────────
    sem_match = [s for s in sugestoes if s.get("selecao_automatica") is None]
    if sem_match:
        r += 1
        ws.cell(r, 1, "ITENS SEM MATCHING SINAPI").font = Font(bold=True, size=11, color="C0392B")
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        r += 1

        for h in headers[:5]:
            cell = ws.cell(r, headers.index(h) + 1, h)
            cell.font = Font(bold=True, color="C0392B")
            cell.fill = sem_match_fill
            cell.border = thin_border
        r += 1

        for s in sem_match:
            ws.cell(r, 1, s.get("id_cad", "")).border = thin_border
            ws.cell(r, 2, s.get("tipo", "")).border = thin_border
            ws.cell(r, 3, s.get("item_original", "")[:80]).border = thin_border
            cell_q = ws.cell(r, 4, float(s.get("quantidade", 0)))
            cell_q.number_format = qty_fmt
            cell_q.border = thin_border
            ws.cell(r, 5, s.get("unidade", "un")).border = thin_border
            r += 1

    # ── Rodapé ─────────────────────────────────────────────────────────
    r += 1
    ws.cell(r, 1, f"Total itens orçados: {resumo.get('total_itens', 0)}  |  "
                  f"Subtotal: {fmt_moeda(subtotal)}  |  "
                  f"BDI: {taxa_bdi:.1f}%  |  "
                  f"Total: {fmt_moeda(total_geral)}  |  "
                  f"Itens sem matching: {resumo.get('total_sem_itens', 0)}").font = Font(italic=True, size=9)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
    r += 1
    ws.cell(r, 1, "Documento gerado automaticamente | Fonte: SINAPI Referência | Matching: Keyword + LLM").font = Font(italic=True, size=9, color="7F8C8D")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)

    # ── Larguras das colunas ───────────────────────────────────────────
    col_widths = {
        1: 14,   # ITEM
        2: 14,   # TIPO
        3: 45,   # DESCRIÇÃO
        4: 8,    # QTD
        5: 6,    # UN
        6: 16,   # COD SINAPI
        7: 55,   # DESCRIÇÃO SINAPI
        8: 18,   # PREÇO UNIT. (R$ 1.234,56)
        9: 18,   # TOTAL
        10: 12,  # STATUS
    }
    for col, width in col_widths.items():
        ws.column_dimensions[get_column_letter(col)].width = width

    # ── Freeze pane ────────────────────────────────────────────────────
    ws.freeze_panes = "A8"

    wb.save(output_path)
    return output_path


def exportar_pdf(
    sugestoes: List[Dict],
    orcamento: Dict,
    metadados: Optional[Dict] = None,
    output_path: str = "orcamento.pdf",
) -> str:
    """
    Exporta planilha de orcamento para PDF formatado (reportlab).

    Args:
        sugestoes: Saida do gerar_sugestoes_orcamento()
        orcamento: Saida do calcular_orcamento_final()
        metadados: Metadados da obra (opcional)
        output_path: Caminho para salvar o PDF

    Returns:
        Caminho do arquivo gerado
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, PageBreak,
    )
    from reportlab.lib.units import cm, mm

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm,
        leftMargin=2*cm, rightMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        'Titulo', parent=styles['Title'],
        fontSize=16, spaceAfter=6, spaceBefore=12,
    )
    estilo_sub = ParagraphStyle(
        'Sub', parent=styles['Heading2'],
        fontSize=11, spaceAfter=4, spaceBefore=10,
    )
    estilo_normal = ParagraphStyle(
        'Normal', parent=styles['Normal'],
        fontSize=8, spaceAfter=2,
    )
    estilo_resumo = ParagraphStyle(
        'Resumo', parent=styles['Normal'],
        fontSize=10, spaceAfter=6, spaceBefore=12,
    )

    elements = []

    # Titulo
    nome_obra = (metadados or {}).get("nome", "Orcamento SINAPI")
    elements.append(Paragraph(f"ORCAMENTO - {nome_obra}", estilo_titulo))
    elements.append(Paragraph(
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        estilo_normal,
    ))
    elements.append(Spacer(1, 12))

    # Tabela de itens
    elements.append(Paragraph("ITENS ORCADOS", estilo_sub))
    elements.append(Spacer(1, 6))

    cabecalho = ["Item", "Descricao", "Qtd", "Un", "Cod. SINAPI", "Preco Un.", "Total"]
    dados_tabela = [cabecalho]

    itens_orcados = orcamento.get("itens", [])
    orcado_ids = {i.get("id_cad") for i in itens_orcados}

    for s in sugestoes:
        id_cad = s.get("id_cad", "")
        item_original = s.get("item_original", "")
        quantidade = s.get("quantidade", 0)
        unidade = s.get("unidade", "un")
        auto = s.get("selecao_automatica")
        opcoes = s.get("opcoes_sinapi", [])

        if auto is not None and auto < len(opcoes):
            escolha = opcoes[auto]
            cod = escolha.get("codigo", "")
            preco = float(escolha.get("preco_unitario", 0))
            total = quantidade * preco
            desc = escolha.get("descricao", "").split("| Descrição: ")[-1][:80]
            dados_tabela.append([
                id_cad,
                Paragraph(item_original[:50], estilo_normal),
                f"{quantidade:.2f}",
                unidade,
                cod,
                f"R$ {preco:.2f}",
                f"R$ {total:.2f}",
            ])
        else:
            dados_tabela.append([
                id_cad,
                Paragraph(item_original[:50], estilo_normal),
                f"{quantidade:.2f}",
                unidade,
                "---",
                "---",
                "---",
            ])

    larguras = [2.5*cm, 5*cm, 1.5*cm, 1*cm, 2.5*cm, 2*cm, 2*cm]
    tabela = Table(dados_tabela, colWidths=larguras, repeatRows=1)
    estilo_tabela = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F4F4")]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
    tabela.setStyle(estilo_tabela)
    elements.append(tabela)

    elements.append(Spacer(1, 20))

    # Resumo financeiro
    elements.append(Paragraph("RESUMO FINANCEIRO", estilo_sub))
    resumo = orcamento.get("resumo", {})

    dados_resumo = [
        ["Subtotal", f"R$ {resumo.get('subtotal', 0):.2f}"],
        [f"BDI ({resumo.get('taxa_bdi_percentual', 0):.1f}%)",
         f"R$ {resumo.get('valor_bdi', 0):.2f}"],
        ["TOTAL GERAL", f"R$ {resumo.get('total_geral', 0):.2f}"],
        ["Itens sem matching SINAPI", str(resumo.get('total_sem_itens', 0))],
    ]
    tabela_resumo = Table(dados_resumo, colWidths=[10*cm, 6*cm])
    estilo_resumo_t = TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F2F4F4")),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor("#D5F5E3")),
        ('FONTNAME', (0, 2), (1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 2), (1, 2), 12),
    ])
    tabela_resumo.setStyle(estilo_resumo_t)
    elements.append(tabela_resumo)

    elements.append(Spacer(1, 12))

    # Itens sem matching
    sem_match = [s for s in sugestoes if s.get("selecao_automatica") is None]
    if sem_match:
        elements.append(Paragraph("ITENS SEM MATCHING SINAPI", estilo_sub))
        for s in sem_match:
            elements.append(Paragraph(
                f"  - {s.get('id_cad', '')}: {s.get('item_original', '')} "
                f"({s.get('quantidade', 0)} {s.get('unidade', 'un')})",
                estilo_normal,
            ))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        f"Documento gerado automaticamente em {datetime.now().strftime('%d/%m/%Y %H:%M')} "
        f"| Fonte: SINAPI Referencia 12/2025 | Matching: Keyword + LLM (gemma4)",
        estilo_normal,
    ))

    doc.build(elements)
    return output_path
