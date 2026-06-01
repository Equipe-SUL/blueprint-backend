import gradio as gr
import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")
import django
django.setup()


def processar_dxf(filepath: str, modo: str):
    from apps.projetos.ai.cad.engine import process_dxf as cad_process
    from apps.projetos.ai.extracaocalculo.dxf_core import extrair_dxf
    from dataclasses import asdict

    if not filepath:
        return "Nenhum arquivo", "{}", "{}", "{}", "{}", "{}"

    # --- CAD Engine ---
    cad_result = cad_process(filepath)
    cad_ok = cad_result.success

    # --- dxf_core (estrutural) ---
    dados_estruturais = {}
    estrutural_ok = False
    try:
        memorial = extrair_dxf(filepath)
        dados_estruturais_raw = asdict(memorial)
        dados_estruturais_raw.pop("entidades", None)

        def sanitize(obj):
            if isinstance(obj, dict):
                return {k: sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize(v) for v in obj]
            elif isinstance(obj, tuple):
                return tuple(sanitize(v) for v in obj)
            elif hasattr(obj, "item") and callable(obj.item):
                return obj.item()
            return obj

        dados_estruturais = sanitize(dados_estruturais_raw)
        estrutural_ok = True
    except Exception as e:
        dados_estruturais = {"erro": str(e)}

    # --- Montar resumo ---
    if modo == "Combinado (CAD + Estrutural)" or modo == "Apenas CAD Engine":
        stats = dict(cad_result.stats) if cad_ok else {}
        if estrutural_ok:
            stats["entidades_dxf_core"] = dados_estruturais.get("total_entidades", 0)
            stats["camadas_dxf_core"] = len(dados_estruturais.get("resumo_por_camada", {}))
        stats["success"] = cad_ok
    else:
        stats = dados_estruturais

    stats_json = json.dumps(stats, indent=2, ensure_ascii=False, default=str)

    # --- GeoJSON ---
    geojson_data = cad_result.geojson if cad_ok else None
    geojson_json = json.dumps(geojson_data, indent=2, ensure_ascii=False) if geojson_data else "{}"

    # --- Ambientes ---
    rooms_data = cad_result.rooms if cad_ok else []
    rooms_json = json.dumps(rooms_data, indent=2, ensure_ascii=False) if rooms_data else "[]"

    # --- Adjacencia ---
    adj_data = cad_result.metrics.adjacency if cad_ok and cad_result.metrics else {}
    adj_json = json.dumps(
        {str(k): v for k, v in adj_data.items()},
        indent=2, ensure_ascii=False,
    ) if adj_data else "{}"

    # --- Topologia ---
    topo = {}
    if cad_ok and cad_result.topology:
        comps = cad_result.topology.connected_components()
        topo = {
            "vertices": cad_result.topology.node_count(),
            "arestas": cad_result.topology.edge_count(),
            "componentes_conexos": len(comps),
            "tamanhos_componentes": [len(c) for c in comps[:10]],
        }
    topo_json = json.dumps(topo, indent=2, ensure_ascii=False) if topo else "{}"

    # --- Estrutural (camadas) ---
    if estrutural_ok:
        resumo = dados_estruturais.get("resumo_por_camada", {})
        resumo_simple = {
            k: {
                "categoria": v.get("categoria", ""),
                "qtd": v.get("quantidade", 0),
                "area_m2": v.get("area_total_m2", 0),
                "volume_m3": v.get("volume_m3", 0),
            }
            for k, v in resumo.items()
        }
        estrutural_json = json.dumps(resumo_simple, indent=2, ensure_ascii=False)
    else:
        estrutural_json = "{}"

    return stats_json, rooms_json, geojson_json, adj_json, topo_json, estrutural_json


def gerar_memorial_pdf(filepath: str):
    if not filepath:
        return None, "Nenhum arquivo selecionado"

    from apps.projetos.ai.cad.engine import process_dxf as cad_process
    from langchain_core.messages import SystemMessage, HumanMessage
    from apps.projetos.ai.client import get_chat_llm
    from apps.projetos.ai.prompts_descritivo import (
        SYSTEM_PROMPT_AUDITOR,
        USER_PROMPT_MEMORIAL_DESCRITIVO,
    )
    from apps.projetos.ai.nbrs import inject_nbrs_into_prompt
    contexto_obra = f"{metadados['tipo_construcao']} {metadados['nome']} ambientes: {', '.join(a['nome'] for a in ambientes_final)}"
    system_prompt = inject_nbrs_into_prompt(SYSTEM_PROMPT_AUDITOR, contexto_obra=contexto_obra, k=5)
    from apps.projetos.ai.services.pdf_generator import gerar_pdf_memorial_descritivo

    import json, os, uuid

    cad_result = cad_process(filepath)
    if not cad_result.success:
        return None, f"Falha no CAD Engine: {cad_result.error}"

    # ambientes_final (mesma logica do nodes_descritivo)
    ambientes_final = []
    for room in cad_result.rooms:
        idx = room["index"]
        if cad_result.used_text_fallback and room.get("area_m2") is not None:
            area_m2 = room["area_m2"]
            perimetro_m = 0.0
        elif cad_result.metrics and idx < len(cad_result.metrics.rooms):
            rm = cad_result.metrics.rooms[idx]
            area_m2 = rm.area_m2 if rm else 0.0
            perimetro_m = rm.perimeter_m if rm else 0.0
        else:
            area_m2 = 0.0
            perimetro_m = 0.0
        ambientes_final.append({
            "nome": room.get("nome_sugerido", f"Ambiente {idx+1}"),
            "area_m2": area_m2,
            "perimetro_m": perimetro_m,
            "pe_direito_m": 0.0,
        })

    metadados = {
        "nome": "Planta Geminada 48,60m²",
        "localizacao": "Não informada",
        "tipo_construcao": "Residencial Geminado",
        "padrao_acabamento": "Médio",
    }

    full_report = cad_result.full_report or {}
    blocos_por_tipo = full_report.get("blocos_por_tipo", {})
    blocos = full_report.get("blocos_detalhados", [])
    blocos_str = json.dumps({"por_tipo": blocos_por_tipo, "detalhados": blocos}, ensure_ascii=False, indent=2)
    dimensoes_str = json.dumps(full_report.get("dimensoes", []), ensure_ascii=False, indent=2)
    full_report_compact = {
        "camadas": full_report.get("camadas", {}),
        "blocos_por_tipo": blocos_por_tipo,
        "total_blocos": full_report.get("total_blocos", 0),
        "total_dimensoes": full_report.get("total_dimensoes", 0),
        "total_textos": full_report.get("total_textos", 0),
        "textos_por_camada": full_report.get("textos_por_camada", {}),
        "total_entidades": full_report.get("total_entidades", 0),
        "unidade": full_report.get("unidade", ""),
    }
    fallback_msg = "ATIVADO: áreas dos ambientes vieram dos textos TXT_ÁREA (fonte primária)" if cad_result.used_text_fallback else "DESATIVADO: áreas vieram do cálculo geométrico"

    user_prompt = USER_PROMPT_MEMORIAL_DESCRITIVO.format(
        metadados_obra=json.dumps(metadados, ensure_ascii=False, indent=2),
        ambientes=json.dumps(ambientes_final, ensure_ascii=False, indent=2),
        textos_legenda=json.dumps(cad_result.texts or [], ensure_ascii=False, indent=2),
        resumo_por_camada=json.dumps(full_report.get("camadas", {}), ensure_ascii=False, indent=2),
        estatisticas=json.dumps(cad_result.stats, ensure_ascii=False, indent=2),
        cad_polygons_geojson=json.dumps(cad_result.geojson or {}, ensure_ascii=False, indent=2),
        cad_adjacency=json.dumps({}, ensure_ascii=False, indent=2),
        cad_topology_stats=json.dumps({}, ensure_ascii=False, indent=2),
        cad_blocos=blocos_str,
        cad_dimensoes=dimensoes_str,
        cad_full_report=json.dumps(full_report_compact, ensure_ascii=False, indent=2),
        cad_used_text_fallback=fallback_msg,
    )

    llm = get_chat_llm()
    mensagens = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    resposta = llm.invoke(mensagens)
    texto_resposta = resposta.content.strip()

    # Parse JSON da resposta
    texto_limpo = texto_resposta
    if "```json" in texto_limpo:
        texto_limpo = texto_limpo.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in texto_limpo:
        texto_limpo = texto_limpo.split("```", 1)[1].split("```", 1)[0]
    try:
        memorial_descritivo = json.loads(texto_limpo.strip())
    except json.JSONDecodeError:
        memorial_descritivo = {
            "dados_gerais": metadados,
            "resposta_bruta_llm": texto_resposta,
            "ambientes": ambientes_final,
            "confianca_analise": "baixa",
        }

    pdf_dir = "pdfs"
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f"memorial_{uuid.uuid4().hex[:8]}.pdf")

    gerar_pdf_memorial_descritivo(
        memorial_dict=memorial_descritivo,
        metadados=metadados,
        output_path=pdf_path,
    )

    confianca = memorial_descritivo.get("confianca_analise", "media")
    inconsistencias = len(memorial_descritivo.get("inconsistencias_detectadas", []))
    n_ambientes = len(memorial_descritivo.get("ambientes", []))
    resumo_texto = f"Confiança: {confianca} | Ambientes: {n_ambientes} | Inconsistências: {inconsistencias} | PDF: {os.path.getsize(pdf_path)/1024:.1f} KB"

    return pdf_path, resumo_texto


ESTADO_ORCAMENTO = {}  # cache: filepath -> (sugestoes, orcamento)


def processar_orcamento(filepath: str):
    if not filepath:
        return [], "Nenhum arquivo", "Nenhum arquivo selecionado"

    from apps.projetos.ai.extracaocalculo.dxf_core import extrair_dxf
    from apps.projetos.ai.cad.engine import process_dxf as cad_process
    from apps.projetos.ai.services.adapter import adaptar_memorial_para_orcamento, adaptar_blocos_para_orcamento
    from apps.projetos.ai.services.orcamento_service import gerar_sugestoes_orcamento, calcular_orcamento_final
    from dataclasses import asdict
    import json

    # 1. Extrair dados estruturais (dxf_core) + blocos (CAD engine)
    try:
        memorial = extrair_dxf(filepath)
        dados_raw = asdict(memorial)
        def sanitize(obj):
            if isinstance(obj, dict):
                return {k: sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize(v) for v in obj]
            elif isinstance(obj, tuple):
                return tuple(sanitize(v) for v in obj)
            elif hasattr(obj, "item") and callable(obj.item):
                return obj.item()
            return obj
        dados_estruturais = sanitize(dados_raw)
    except Exception as e:
        return [], f"Erro na extração: {e}", "Falha"

    # 2. CAD engine para blocos semânticos
    cad_result = cad_process(filepath)
    blocos_cad = adaptar_blocos_para_orcamento(cad_result.full_report or {}) if cad_result.success else []

    # 3. Adaptar estruturais + mesclar com blocos CAD
    itens_cad = adaptar_memorial_para_orcamento(dados_estruturais)
    ids_existentes = {i["id"] for i in itens_cad}
    for b in blocos_cad:
        if b["id"] not in ids_existentes:
            itens_cad.append(b)
            ids_existentes.add(b["id"])

    # 3. Buscar SINAPI
    sugestoes = gerar_sugestoes_orcamento(itens_cad, usar_llm=True)

    # 4. Calcular orçamento
    orcamento = calcular_orcamento_final(sugestoes, taxa_bdi=25.0)

    # Cache para export
    ESTADO_ORCAMENTO[filepath] = (sugestoes, orcamento)

    # 5. Montar dataframe
    tabela = []
    for s in sugestoes:
        id_cad = s.get("id_cad", "")
        desc = s.get("item_original", "")
        qtd = s.get("quantidade", 0)
        un = s.get("unidade", "un")
        auto = s.get("selecao_automatica")
        opcoes = s.get("opcoes_sinapi", [])
        if auto is not None and auto < len(opcoes):
            escolha = opcoes[auto]
            cod = escolha.get("codigo", "")
            preco = float(escolha.get("preco_unitario", 0))
            total = round(qtd * preco, 2)
            desc_sinapi = escolha.get("descricao", "").split("| Descrição: ")[-1][:60]
            tabela.append([
                id_cad, desc, qtd, un, "✅ " + desc_sinapi, cod,
                f"R$ {preco:.2f}", f"R$ {total:.2f}",
            ])
        else:
            tabela.append([id_cad, desc, qtd, un, "❌ Sem matching", "", "", ""])

    # Salvar automaticamente CSV + PDF
    from apps.projetos.ai.services.export_orcamento import exportar_csv as _exp_csv, exportar_pdf as _exp_pdf
    import datetime
    csv_dir = "csv"
    pdf_dir = "pdfs"
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(pdf_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_auto = os.path.join(csv_dir, f"orcamento_{ts}.csv")
    pdf_auto = os.path.join(pdf_dir, f"orcamento_{ts}.pdf")
    try:
        _exp_csv(sugestoes, orcamento, csv_auto)
        _exp_pdf(sugestoes, orcamento, {"nome": "Orcamento SINAPI"}, pdf_auto)
        csv_ok = os.path.getsize(csv_auto)
        pdf_ok = os.path.getsize(pdf_auto)
    except Exception as e:
        csv_ok = 0
        pdf_ok = 0

    resumo = orcamento.get("resumo", {})
    linhas_resumo = (
        f"Itens orçados: {resumo.get('total_itens', 0)} | "
        f"Sem matching: {resumo.get('total_sem_itens', 0)} | "
        f"Subtotal: R$ {resumo.get('subtotal', 0):.2f} | "
        f"BDI ({resumo.get('taxa_bdi_percentual', 0):.1f}%): R$ {resumo.get('valor_bdi', 0):.2f} | "
        f"TOTAL: R$ {resumo.get('total_geral', 0):.2f} | "
        f"CSV: {csv_ok/1024:.1f}KB | PDF: {pdf_ok/1024:.1f}KB"
    )

    return tabela, linhas_resumo, "Orçamento gerado com sucesso!"


def _get_orcamento_cache(filepath: str):
    """Retorna (sugestoes, orcamento) do cache ou gera novamente."""
    if filepath in ESTADO_ORCAMENTO:
        return ESTADO_ORCAMENTO[filepath]
    return None, None


def exportar_orcamento_csv(filepath: str):
    if not filepath:
        return None
    import tempfile, os
    from apps.projetos.ai.services.export_orcamento import exportar_csv
    sugestoes, orcamento = _get_orcamento_cache(filepath)
    if not sugestoes:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", dir=".")
    nome = tmp.name
    tmp.close()
    exportar_csv(sugestoes, orcamento, nome)
    return nome


def exportar_orcamento_pdf(filepath: str):
    if not filepath:
        return None
    import tempfile, os
    from apps.projetos.ai.services.export_orcamento import exportar_pdf
    sugestoes, orcamento = _get_orcamento_cache(filepath)
    if not sugestoes:
        return None
    metadados = {"nome": "Orçamento SINAPI - Planta Geminada"}
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=".")
    nome = tmp.name
    tmp.close()
    exportar_pdf(sugestoes, orcamento, metadados, nome)
    return nome


with gr.Blocks(title="Blueprint3 - CAD Engine Tester") as demo:
    gr.Markdown("""
    # 🏗️ Blueprint3 - CAD Engine Tester
    Teste o novo engine de parser com **polygonização, healing, topologia e adjacência**.
    """)

    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(label="Upload DXF", file_types=[".dxf"], type="filepath")

            modo = gr.Radio(
                choices=[
                    "Combinado (CAD + Estrutural)",
                    "Apenas CAD Engine",
                ],
                label="Modo de Exibição",
                value="Combinado (CAD + Estrutural)",
            )

            submit_btn = gr.Button("🚀 Processar", variant="primary", size="lg")

            gr.Markdown("""
            ---
            ### 💡 Sobre o CAD Engine

            **Pipeline completo:**
            1. **Parser** → blocos, XREF, OCS, unidades
            2. **Flatten** → curvas adaptativas
            3. **Healing** → snap + merge de vértices
            4. **Polygonização** → segmentos → polígonos
            5. **Validação** → repair de polígonos inválidos
            6. **Métricas** → área, perímetro, adjacência
            7. **Classificação** → texto → ambiente
            8. **Topologia** → grafo networkx

            **Resultado:** LLM recebe dados estruturais + geometria enriquecida → PDF completo.
            """)

        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.Tab("📊 Stats"):
                    output_stats = gr.Code(label="Métricas", language="json")
                with gr.Tab("🏠 Ambientes"):
                    output_rooms = gr.Code(label="Ambientes Detectados", language="json")
                with gr.Tab("🗺️ GeoJSON"):
                    output_geojson = gr.Code(label="GeoJSON", language="json")
                with gr.Tab("🔗 Adjacência"):
                    output_adj = gr.Code(label="Matriz de Adjacência", language="json")
                with gr.Tab("🌐 Topologia"):
                    output_topo = gr.Code(label="Grafo de Topologia", language="json")
                with gr.Tab("🧱 Estrutural"):
                    output_estrutural = gr.Code(label="Camadas Estruturais (dxf_core)", language="json")
                with gr.Tab("📄 Memorial PDF"):
                    gr.Markdown("""
                    ### Gerar Memorial Descritivo Completo

                    Executa o pipeline completo: CAD Engine → LLM (gemma4:31b-cloud) → PDF.
                    Pode levar **30-60 segundos** dependendo da fila da Ollama Cloud.
                    """)
                    memorial_status = gr.Textbox(label="Status", value="Aguardando...", interactive=False)
                    memorial_pdf = gr.File(label="📥 Download do PDF", type="filepath")
                    memorial_btn = gr.Button("🚀 Gerar Memorial PDF", variant="primary", size="lg")
                with gr.Tab("💰 Orçamento"):
                    gr.Markdown("""
                    ### Orçamento SINAPI

                    1. Processa o DXF → extrai quantitativos estruturais
                    2. Busca códigos SINAPI por keyword + LLM (gemma4)
                    3. Gera orçamento com BDI
                    """)
                    orc_status = gr.Textbox(label="Status", value="Aguardando...", interactive=False)
                    with gr.Row():
                        orc_btn = gr.Button("🚀 Gerar Orçamento", variant="primary", size="lg", scale=1)
                        export_csv_btn = gr.Button("📥 Exportar CSV", variant="secondary", size="lg", scale=1)
                        export_pdf_btn = gr.Button("📥 Exportar PDF", variant="secondary", size="lg", scale=1)
                    orc_tabela = gr.Dataframe(
                        headers=["Item", "Descrição CAD", "Qtd", "Un", "Match SINAPI", "Cod.", "Preço Un.", "Total"],
                        label="Itens Orçados",
                        interactive=False,
                    )
                    orc_resumo = gr.Textbox(label="Resumo Financeiro", interactive=False)
                    orc_download = gr.File(label="Download", type="filepath", visible=False)

    submit_btn.click(
        fn=processar_dxf,
        inputs=[file_input, modo],
        outputs=[output_stats, output_rooms, output_geojson, output_adj, output_topo, output_estrutural],
    )

    orc_btn.click(
        fn=processar_orcamento,
        inputs=[file_input],
        outputs=[orc_tabela, orc_resumo, orc_status],
    )

    export_csv_btn.click(
        fn=exportar_orcamento_csv,
        inputs=[file_input],
        outputs=[orc_download],
    ).then(
        lambda: gr.update(visible=True), None, orc_download,
    )

    export_pdf_btn.click(
        fn=exportar_orcamento_pdf,
        inputs=[file_input],
        outputs=[orc_download],
    ).then(
        lambda: gr.update(visible=True), None, orc_download,
    )

if __name__ == "__main__":
    import socket
    def find_free_port(start=7861, end=7900):
        for port in range(start, end):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
        return 7861
    port = find_free_port()
    print(f"\n   Abrindo em http://127.0.0.1:{port}\n")
    demo.launch(server_name="127.0.0.1", server_port=port, show_error=True, theme=gr.themes.Soft())
