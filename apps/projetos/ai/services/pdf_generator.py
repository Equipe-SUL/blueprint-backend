"""
pdf_generator.py
=================
Gera PDF formatado do Memorial Descritivo usando reportlab.

Produz um documento profissional com:
  - Cabeçalho com título e dados da obra
  - Seções estruturadas (ambientes, elementos, instalações)
  - Rodapé com data de geração
"""

import os
from datetime import datetime
from typing import Dict, List, Optional


def gerar_pdf_memorial_descritivo(
    memorial_dict: dict,
    metadados: dict,
    output_path: str,
) -> str:
    """
    Gera PDF formatado do Memorial Descritivo.

    Parâmetros:
        memorial_dict : JSON do memorial descritivo (saída do Nó 3)
        metadados     : Metadados da obra
        output_path   : Caminho absoluto para salvar o PDF

    Retorna:
        Caminho do PDF gerado
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

    # ── Configuração do documento ────────────────────────────────────────
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    # ── Estilos ──────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        "Titulo",
        parent=styles["Title"],
        fontSize=18,
        textColor=HexColor("#1a3c5e"),
        spaceAfter=6,
        alignment=TA_CENTER,
    )

    subtitulo_style = ParagraphStyle(
        "Subtitulo",
        parent=styles["Normal"],
        fontSize=11,
        textColor=HexColor("#4a6d8c"),
        spaceAfter=12,
        alignment=TA_CENTER,
    )

    secao_style = ParagraphStyle(
        "Secao",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=HexColor("#1a3c5e"),
        spaceBefore=16,
        spaceAfter=8,
        borderWidth=1,
        borderColor=HexColor("#1a3c5e"),
        borderPadding=4,
    )

    subsecao_style = ParagraphStyle(
        "Subsecao",
        parent=styles["Heading3"],
        fontSize=11,
        textColor=HexColor("#2d5f8a"),
        spaceBefore=10,
        spaceAfter=4,
    )

    corpo_style = ParagraphStyle(
        "Corpo",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )

    alerta_style = ParagraphStyle(
        "Alerta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=HexColor("#c0392b"),
        spaceAfter=4,
        leftIndent=12,
    )

    rodape_style = ParagraphStyle(
        "Rodape",
        parent=styles["Normal"],
        fontSize=8,
        textColor=HexColor("#777777"),
        alignment=TA_CENTER,
    )

    # ── Construir conteúdo ───────────────────────────────────────────────
    elementos = []

    # Cabeçalho
    elementos.append(Paragraph("MEMORIAL DESCRITIVO", titulo_style))

    dados_gerais = memorial_dict.get("dados_gerais", {})
    nome_obra = dados_gerais.get("nome_obra", metadados.get("nome", "Obra"))
    localizacao = dados_gerais.get("localizacao", metadados.get("localizacao", ""))
    tipo = dados_gerais.get("tipo_construcao", metadados.get("tipo_construcao", ""))
    padrao = dados_gerais.get("padrao_acabamento", metadados.get("padrao_acabamento", ""))

    elementos.append(Paragraph(f"{nome_obra}", subtitulo_style))
    elementos.append(HRFlowable(
        width="100%", thickness=1, color=HexColor("#1a3c5e"),
        spaceAfter=12, spaceBefore=4,
    ))

    # Dados Gerais
    elementos.append(Paragraph("1. DADOS GERAIS", secao_style))

    info_table_data = [
        ["Obra:", nome_obra],
        ["Localização:", localizacao],
        ["Tipo de Construção:", tipo],
        ["Padrão de Acabamento:", padrao],
    ]
    info_table = Table(info_table_data, colWidths=[5 * cm, 11 * cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(info_table)

    desc_geral = dados_gerais.get("descricao_geral", "")
    if desc_geral:
        elementos.append(Spacer(1, 8))
        elementos.append(Paragraph(desc_geral, corpo_style))

    # Ambientes
    ambientes = memorial_dict.get("ambientes", [])
    if ambientes:
        elementos.append(Paragraph("2. AMBIENTES", secao_style))

        for i, amb in enumerate(ambientes, 1):
            nome_amb = amb.get("nome", f"Ambiente {i}")
            area = amb.get("area_m2", 0)
            perim = amb.get("perimetro_m", 0)
            pd = amb.get("pe_direito_m", 0)

            elementos.append(Paragraph(f"2.{i} {nome_amb}", subsecao_style))

            # Tabela de dados do ambiente
            amb_data = [
                ["Área:", f"{area:.2f} m²",
                 "Perímetro:", f"{perim:.2f} m",
                 "Pé-direito:", f"{pd:.2f} m"],
            ]
            amb_table = Table(amb_data, colWidths=[3 * cm, 2.5 * cm, 3 * cm, 2.5 * cm, 3 * cm, 2.5 * cm])
            amb_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, 0), "Helvetica-Bold"),
                ("FONTNAME", (4, 0), (4, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elementos.append(amb_table)

            desc_amb = amb.get("descricao", "")
            if desc_amb:
                elementos.append(Paragraph(desc_amb, corpo_style))

            elems_ident = amb.get("elementos_identificados", [])
            if elems_ident:
                lista = ", ".join(elems_ident)
                elementos.append(Paragraph(
                    f"<b>Elementos identificados:</b> {lista}", corpo_style
                ))

            obs_amb = amb.get("observacoes", "")
            if obs_amb:
                elementos.append(Paragraph(
                    f"<i>Obs.: {obs_amb}</i>", corpo_style
                ))

    # Elementos Estruturais
    elems_est = memorial_dict.get("elementos_estruturais", {})
    if elems_est:
        elementos.append(Paragraph("3. ELEMENTOS ESTRUTURAIS", secao_style))

        mapa_nomes = {
            "fundacoes": "Fundações",
            "pilares": "Pilares",
            "vigas": "Vigas",
            "lajes": "Lajes",
            "paredes": "Paredes / Alvenaria",
            "esquadrias": "Esquadrias (Portas e Janelas)",
        }

        for chave, nome_display in mapa_nomes.items():
            dados = elems_est.get(chave, {})
            if not dados:
                continue

            desc = dados.get("descricao", "")
            qtd = dados.get("quantidade", 0)
            area = dados.get("area_total_m2", 0)
            comp = dados.get("comprimento_total_m", 0)
            area_liq = dados.get("area_liquida_m2", 0)
            vol = dados.get("volume_m3", 0)
            obs = dados.get("observacoes", "")

            elementos.append(Paragraph(f"3.x {nome_display}", subsecao_style))

            if desc:
                elementos.append(Paragraph(desc, corpo_style))

            # Montar linha de quantitativos
            quants = []
            if qtd:
                quants.append(f"Quantidade: {qtd}")
            if area:
                quants.append(f"Área: {area:.2f} m²")
            if comp:
                quants.append(f"Comprimento: {comp:.2f} m")
            if area_liq:
                quants.append(f"Área líquida: {area_liq:.2f} m²")
            if vol:
                quants.append(f"Volume: {vol:.4f} m³")

            if quants:
                elementos.append(Paragraph(
                    f"<b>Quantitativos:</b> {' | '.join(quants)}", corpo_style
                ))

            if obs:
                elementos.append(Paragraph(f"<i>Obs.: {obs}</i>", corpo_style))

    # Instalações
    instalacoes = memorial_dict.get("instalacoes", {})
    if instalacoes:
        elementos.append(Paragraph("4. INSTALAÇÕES", secao_style))

        for tipo_inst, dados in instalacoes.items():
            if isinstance(dados, dict):
                identificado = dados.get("identificado", False)
                desc = dados.get("descricao", "")
                detalhes = dados.get("detalhes", "")

                status = "Identificado na planta" if identificado else "Não identificado na planta"
                nome_inst = tipo_inst.replace("_", " ").title()

                elementos.append(Paragraph(f"4.x {nome_inst}", subsecao_style))
                elementos.append(Paragraph(f"<b>Status:</b> {status}", corpo_style))

                if desc:
                    elementos.append(Paragraph(desc, corpo_style))
                if detalhes:
                    elementos.append(Paragraph(detalhes, corpo_style))

    # Observações Técnicas
    obs_tecnicas = memorial_dict.get("observacoes_tecnicas", [])
    if obs_tecnicas:
        elementos.append(Paragraph("5. OBSERVAÇÕES TÉCNICAS", secao_style))
        for obs in obs_tecnicas:
            elementos.append(Paragraph(f"• {obs}", corpo_style))

    # Inconsistências
    inconsistencias = memorial_dict.get("inconsistencias_detectadas", [])
    if inconsistencias:
        elementos.append(Paragraph("6. INCONSISTÊNCIAS DETECTADAS", secao_style))
        for inc in inconsistencias:
            elementos.append(Paragraph(f"⚠ {inc}", alerta_style))

    # Rodapé
    elementos.append(Spacer(1, 30))
    elementos.append(HRFlowable(
        width="100%", thickness=0.5, color=HexColor("#cccccc"),
        spaceAfter=8, spaceBefore=8,
    ))

    confianca = memorial_dict.get("confianca_analise", "N/A")
    data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M")

    elementos.append(Paragraph(
        f"Documento gerado automaticamente em {data_geracao} | "
        f"Confiança da análise: {confianca} | "
        f"Sistema Blueprint Backend",
        rodape_style,
    ))

    # ── Gerar PDF ────────────────────────────────────────────────────────
    doc.build(elementos)
    return output_path
