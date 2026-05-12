"""
Teste do pipeline LangGraph completo.

Uso:
    python scripts_teste/testar_pipeline.py

Testa:
  1. Pipeline completo (DXF → Extração → Classificação → ... → Orçamento)
  2. Human-in-the-loop (se houver alertas críticos)
"""
import os
import sys
import json
import django

caminho_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, caminho_raiz)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from apps.projetos.ai.services.pipeline_service import processar_dxf_completo, retomar_pipeline

# Usa o Estrutura.dxf direto do Desktop (ou troque pelo caminho do arquivo)
CAMINHO_DXF = os.path.join(os.path.expanduser('~'), 'Desktop', 'ExtraçãoCalculo', 'Estrutura.dxf')
PROJETO_ID = None  # Sem projeto no banco — BDI = 0%


def imprimir_resultado(resultado):
    """Imprime o resultado do pipeline de forma organizada."""
    print("\n" + "=" * 80)

    if resultado.get("sucesso"):
        print("✅ PIPELINE COMPLETO COM SUCESSO!")

        # Memorial de cálculo
        memorial = resultado.get("memorial_calculo", {})
        resumo = memorial.get("resumo_geral", {})
        print(f"\n📊 RESUMO GERAL:")
        print(f"   Features calculadas: {resumo.get('total_features', 0)}")
        print(f"   Área total: {resumo.get('area_total_m2', 0)} m²")
        print(f"   Perímetro total: {resumo.get('perimetro_total_m', 0)} m")

        # Resumo por categoria
        categorias = memorial.get("resumo_por_categoria", {})
        if categorias:
            print(f"\n📋 POR CATEGORIA:")
            for cat, dados in categorias.items():
                print(f"   {cat}: {dados.get('quantidade', 0)} elementos | "
                      f"área={dados.get('area_m2', 0):.2f} m² | "
                      f"perímetro={dados.get('perimetro_m', 0):.2f} m")

        # Itens adaptados
        itens = resultado.get("itens_adaptados", [])
        if itens:
            print(f"\n🔄 ITENS ADAPTADOS PARA RAG ({len(itens)}):")
            for item in itens:
                print(f"   [{item['id']}] {item['description']} → "
                      f"qty: {item['quantity']} {item['unidade']}")

        # Orçamento
        orcamento = resultado.get("orcamento_final", {})
        resumo_orc = orcamento.get("resumo", {})
        if resumo_orc:
            print(f"\n💰 ORÇAMENTO FINAL:")
            print(f"   Total itens: {resumo_orc.get('total_itens', 0)}")
            print(f"   Subtotal: R$ {resumo_orc.get('subtotal', 0):.2f}")
            print(f"   BDI ({resumo_orc.get('taxa_bdi_percentual', 0)}%): "
                  f"R$ {resumo_orc.get('valor_bdi', 0):.2f}")
            print(f"   TOTAL GERAL: R$ {resumo_orc.get('total_geral', 0):.2f}")

        # Alertas
        alertas = resultado.get("alertas", [])
        if alertas:
            print(f"\n⚠️  ALERTAS ({len(alertas)}):")
            for a in alertas:
                print(f"   • {a}")

    elif resultado.get("pausado"):
        print("⏸️  PIPELINE PAUSADO — HUMAN-IN-THE-LOOP")
        print(f"\n   Thread ID: {resultado.get('thread_id')}")
        print(f"   Etapa: {resultado.get('etapa_atual')}")

        interrupt_info = resultado.get("interrupt_info", {})
        if interrupt_info:
            print(f"\n   📋 Info do interrupt:")
            print(f"   Pergunta: {interrupt_info.get('pergunta', 'N/A')}")
            print(f"   Alertas críticos: {interrupt_info.get('alertas_criticos', [])}")

        alertas = resultado.get("alertas", [])
        if alertas:
            print(f"\n   ⚠️  Alertas ({len(alertas)}):")
            for a in alertas:
                print(f"      • {a}")

        return resultado.get("thread_id")

    else:
        print(f"❌ PIPELINE FALHOU: {resultado.get('erro')}")
        alertas = resultado.get("alertas", [])
        if alertas:
            print(f"\n   ⚠️  Alertas ({len(alertas)}):")
            for a in alertas:
                print(f"      • {a}")

    return None


if __name__ == "__main__":
    print(f"📂 Arquivo: {CAMINHO_DXF}")
    print(f"📂 Existe: {os.path.exists(CAMINHO_DXF)}")
    print(f"🏗️  Projeto ID: {PROJETO_ID}")
    print("=" * 80)

    if not os.path.exists(CAMINHO_DXF):
        print("❌ Arquivo DXF não encontrado! Ajuste a variável CAMINHO_DXF.")
        sys.exit(1)

    # ── Executa o pipeline ──────────────────────────────────────────
    resultado = processar_dxf_completo(CAMINHO_DXF, PROJETO_ID)
    thread_id = imprimir_resultado(resultado)

    # ── Se pausou (HITL), pergunta ao usuário ──────────────────────
    if thread_id:
        print("\n" + "-" * 80)
        decisao = input("👤 Deseja continuar? (continuar/cancelar): ").strip().lower()

        if decisao not in ("continuar", "cancelar"):
            decisao = "cancelar"

        resultado_retomado = retomar_pipeline(thread_id, decisao)
        imprimir_resultado(resultado_retomado)
