"""
export_orcamento.py
===================
Exporta resultados de orcamento SINAPI para CSV e PDF.
"""
import os
import csv
from datetime import datetime
from typing import List, Dict, Optional


def exportar_csv(
    sugestoes: List[Dict],
    orcamento: Dict,
    output_path: str,
) -> str:
    """
    Exporta planilha de orcamento para CSV.

    Args:
        sugestoes: Saida do gerar_sugestoes_orcamento()
        orcamento: Saida do calcular_orcamento_final()
        output_path: Caminho para salvar o CSV

    Returns:
        Caminho do arquivo gerado
    """
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')

        # Cabecalho
        writer.writerow(["ITEM", "TIPO", "DESCRICAO CAD", "QTD", "UN",
                         "COD SINAPI", "DESCRICAO SINAPI", "PRECO UNIT",
                         "TOTAL", "STATUS"])

        # Itens do orcamento
        itens_orcados = orcamento.get("itens", [])
        orcado_ids = {i.get("id_cad") for i in itens_orcados}

        for s in sugestoes:
            id_cad = s.get("id_cad", "")
            item_original = s.get("item_original", "")
            quantidade = s.get("quantidade", 0)
            unidade = s.get("unidade", "un")
            tipo = s.get("tipo", "desconhecido")
            auto = s.get("selecao_automatica")
            opcoes = s.get("opcoes_sinapi", [])

            if auto is not None and auto < len(opcoes):
                # Item com matching SINAPI
                escolha = opcoes[auto]
                writer.writerow([
                    id_cad, tipo, item_original, quantidade, unidade,
                    escolha.get("codigo", ""),
                    escolha.get("descricao", "").split("| Descrição: ")[-1][:120],
                    f"R$ {float(escolha.get('preco_unitario', 0)):.2f}",
                    f"R$ {float(quantidade) * float(escolha.get('preco_unitario', 0)):.2f}",
                    "OK",
                ])
            else:
                # Sem matching
                writer.writerow([
                    id_cad, tipo, item_original, quantidade, unidade,
                    "", "", "R$ 0,00", "R$ 0,00",
                    "SEM MATCH SINAPI",
                ])

        # Linha em branco
        writer.writerow([])

        # Resumo
        resumo = orcamento.get("resumo", {})
        writer.writerow(["RESUMO", "", "", "", "", "", "", "", "", ""])
        writer.writerow(["Total itens orcados", "", resumo.get("total_itens", 0),
                         "", "", "", "", "", "", ""])
        writer.writerow(["Subtotal", "", f"R$ {resumo.get('subtotal', 0):.2f}",
                         "", "", "", "", "", "", ""])
        writer.writerow(["BDI (%)", "", f"{resumo.get('taxa_bdi_percentual', 0):.2f}%",
                         "", "", "", "", "", "", ""])
        writer.writerow(["Valor BDI", "", f"R$ {resumo.get('valor_bdi', 0):.2f}",
                         "", "", "", "", "", "", ""])
        writer.writerow(["TOTAL GERAL", "", f"R$ {resumo.get('total_geral', 0):.2f}",
                         "", "", "", "", "", "", ""])
        writer.writerow(["Itens sem matching", "", resumo.get("total_sem_itens", 0),
                         "", "", "", "", "", "", ""])

        # Data
        writer.writerow([])
        writer.writerow(["Gerado em:", datetime.now().strftime("%d/%m/%Y %H:%M")])

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
