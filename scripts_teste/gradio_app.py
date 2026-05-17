import os
import sys
import tempfile
from dataclasses import asdict

import gradio as gr
import pandas as pd

# Garante que o django/apps esteja acessível se rodar de scripts_teste
caminho_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if caminho_raiz not in sys.path:
    sys.path.insert(0, caminho_raiz)

from apps.projetos.ai.extracaocalculo.dxf_core import extrair_dxf
from apps.projetos.ai.extracaocalculo.dxf_exportadores import exportar_json, exportar_csv, exportar_pdf


def processar_arquivo_dxf(arquivo_dxf):
    """
    Recebe um arquivo DXF upado, extrai via dxf_core e retorna:
    - Resumo em Markdown
    - DataFrame de camadas
    - DataFrame de ambientes
    - Caminhos dos arquivos gerados (JSON, CSV, PDF)
    """
    if arquivo_dxf is None:
        return "❌ Nenhum arquivo enviado.", None, None, None, None, None

    caminho_temp_dxf = arquivo_dxf.name
    nome_base = "resultado_extracao"
    
    # Criar pasta temporária para as saídas
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Extrair dados
        memorial = extrair_dxf(caminho_temp_dxf)
        
        # Gerar relatórios (Json, CSV, PDF)
        caminho_json = os.path.join(temp_dir, f"{nome_base}.json")
        caminho_csv = os.path.join(temp_dir, f"{nome_base}.csv")
        caminho_pdf = os.path.join(temp_dir, f"{nome_base}.pdf")
        
        exportar_json(memorial, caminho_json)
        exportar_csv(memorial, caminho_csv)
        exportar_pdf(memorial, caminho_pdf)
        
        # Montar Resumo Geral
        area = sum(r.area_total_m2 for r in memorial.resumo_por_camada.values())
        perim = sum(r.perimetro_total_m for r in memorial.resumo_por_camada.values())
        vol = sum(r.volume_m3 for r in memorial.resumo_por_camada.values())
        
        resumo_md = f"""
        ### 📊 Totais Gerais
        * **Entidades processadas:** {memorial.total_entidades}
        * **Camadas encontradas:** {len(memorial.resumo_por_camada)}
        * **Ambientes detectados:** {len(memorial.ambientes)}
        * **Área Total Calculada:** {area:.2f} m²
        * **Volume Total:** {vol:.2f} m³
        * **Perímetro Total:** {perim:.2f} m
        """
        
        # Montar DataFrame de Camadas
        lista_camadas = []
        for r in sorted(memorial.resumo_por_camada.values(), key=lambda x: x.camada):
            lista_camadas.append({
                "Camada": r.camada,
                "Categoria": r.categoria,
                "Qtd": r.quantidade,
                "Área (m²)": round(r.area_total_m2, 2),
                "Perímetro (m)": round(r.perimetro_total_m, 2),
                "Comprimento (m)": round(r.comprimento_total_m, 2),
                "Volume (m³)": round(r.volume_m3, 2),
                "Área Líquida (m²)": round(r.area_liquida_m2, 2)
            })
        df_camadas = pd.DataFrame(lista_camadas)
        
        # Montar DataFrame de Ambientes
        lista_amb = []
        for a in memorial.ambientes:
            lista_amb.append({
                "Nome": a.nome,
                "Área (m²)": round(a.area_m2, 2),
                "Perímetro (m)": round(a.perimetro_m, 2),
                "Pé-direito (m)": round(a.pe_direito_m, 2)
            })
        df_ambientes = pd.DataFrame(lista_amb) if lista_amb else pd.DataFrame(columns=["Nome", "Área (m²)", "Perímetro (m)", "Pé-direito (m)"])
        
        return resumo_md, df_camadas, df_ambientes, caminho_json, caminho_csv, caminho_pdf
        
    except Exception as e:
        return f"❌ Erro ao processar arquivo: {str(e)}", None, None, None, None, None


def criar_interface():
    """Constrói a interface Gradio dentro de uma função para evitar que o
    context manager do Blocks rode durante a importação do módulo."""
    with gr.Blocks(title="Extrator DXF Blueprint") as interface:
        gr.Markdown("# 🏗️ Blueprint DXF Extractor UI")
        gr.Markdown("Visualize diretamente como nosso script extrai dados de um arquivo `.dxf` (sem IA na etapa inicial).")
        
        with gr.Row():
            with gr.Column(scale=1):
                file_input = gr.File(label="Envie seu arquivo .dxf", file_types=[".dxf"])
                btn_processar = gr.Button("🔍 Processar DXF", variant="primary")
                
            with gr.Column(scale=2):
                resumo_out = gr.Markdown("### 📊 Totais Gerais\nEnvie um arquivo para ver os resultados.")
        
        with gr.Row():
            df_camadas_out = gr.Dataframe(label="Resumo por Camadas (Estruturas)", interactive=False)
        
        with gr.Row():
            df_ambientes_out = gr.Dataframe(label="Ambientes Encontrados (MTEXT)", interactive=False)
            
        with gr.Row():
            gr.Markdown("### 📥 Downloads")
        with gr.Row():
            file_json = gr.File(label="Memorial JSON")
            file_csv = gr.File(label="Memorial CSV")
            file_pdf = gr.File(label="Relatório PDF")

        # Ações
        btn_processar.click(
            fn=processar_arquivo_dxf,
            inputs=file_input,
            outputs=[resumo_out, df_camadas_out, df_ambientes_out, file_json, file_csv, file_pdf]
        )

    return interface


if __name__ == "__main__":
    # Inicia a interface na porta padrão (7860) e exibe no terminal local
    print("Iniciando interface web Gradio...")
    interface = criar_interface()
    interface.launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=False,
        theme=gr.themes.Soft(),
        ssr_mode=False,
    )
