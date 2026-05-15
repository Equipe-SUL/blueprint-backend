import gradio as gr
import json
import os
from core.engine import process_dxf

def parse_dxf_file(file_path):
    if file_path is None:
        return "Nenhum arquivo enviado."
    
    result = process_dxf(file_path)
    
    if not result.success:
        return f"Erro: {result.error}\n\nStats: {json.dumps(result.stats, indent=2)}"
    
    return json.dumps(result.stats, indent=2, ensure_ascii=False)

with gr.Blocks(title="DXF Parser Tester") as demo:
    gr.Markdown("# DXF Parser Tester")
    gr.Markdown("Faça upload de um arquivo .dxf para processar e ver as métricas extraídas.")
    
    with gr.Row():
        with gr.Column():
            file_input = gr.File(label="Upload DXF", file_types=[".dxf"], type="filepath")
            submit_btn = gr.Button("Processar DXF", variant="primary")
        
        with gr.Column():
            output_stats = gr.Code(language="json", label="Parser Stats & Metrics")
            
    submit_btn.click(
        fn=parse_dxf_file,
        inputs=[file_input],
        outputs=[output_stats]
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, show_error=True)
