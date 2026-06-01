import os, sys, json
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import django
django.setup()

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
DXF = "dxf/casona228m.dxf"
os.makedirs("pdfs", exist_ok=True)
os.makedirs("csv", exist_ok=True)

from apps.projetos.ai.cad.engine import process_dxf as cad_process
from apps.projetos.ai.extracaocalculo.dxf_core import extrair_dxf
from apps.projetos.ai.services.adapter import adaptar_blocos_para_orcamento
from apps.projetos.ai.services.orcamento_service import gerar_sugestoes_orcamento, calcular_orcamento_final
from apps.projetos.ai.services.pdf_generator import gerar_pdf_memorial_descritivo
from apps.projetos.ai.services.export_orcamento import exportar_csv, exportar_pdf
from apps.projetos.ai.client import get_chat_llm
from apps.projetos.ai.prompts_descritivo import SYSTEM_PROMPT_AUDITOR, USER_PROMPT_MEMORIAL_DESCRITIVO
from apps.projetos.ai.nbrs import inject_nbrs_into_prompt
from langchain_core.messages import SystemMessage, HumanMessage
from dataclasses import asdict

DESCRICAO_OBRA = """Projeto arquitetônico de 228m² com arquivos em DWG e PDF. Proposta com ambientes internos em ângulos de 45°, valorizando o design moderno e diferenciado.

A planta conta com 4 quartos, sendo 2 suítes, além de copa-cozinha, sala de estar, banheiros e ampla varanda com garagem integrada.

Inclui ainda um quarto de serviço e banheiro com acesso externo, ideal também para hóspedes, garantindo conforto sem comprometer a privacidade dos moradores."""

if "geminada" in DXF:
    DESCRICAO_OBRA = "Projeto de planta geminada com 48,60m² por unidade, contendo sala, cozinha, quarto, banheiro, área de serviço e varanda. Tipologia repetitiva com duas unidades espelhadas."

# ═══════════════════════════════════════════
# 1/5 - CAD ENGINE
# ═══════════════════════════════════════════
print("="*60)
print("1/5 - CAD ENGINE")
print("="*60)
cad_result = cad_process(DXF)
rooms = len(cad_result.rooms)
blocos = len(cad_result.full_report.get("blocos_por_tipo", {})) if cad_result.full_report else 0
blocos_det = len(cad_result.full_report.get("blocos_detalhados", [])) if cad_result.full_report else 0
print(f"  Rooms: {rooms}")
print(f"  Blocos (tipos): {blocos}")
print(f"  Blocos (detalhados): {blocos_det}")
print(f"  Stats OK: {cad_result.success}")

# ═══════════════════════════════════════════
# 2/5 - DADOS ESTRUTURAIS + BLOCOS CAD
# ═══════════════════════════════════════════
print()
print("="*60)
print("2/5 - DADOS ESTRUTURAIS + BLOCOS CAD")
print("="*60)
print()
memorial = extrair_dxf(DXF)
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
blocos_cad = adaptar_blocos_para_orcamento(cad_result.full_report or {}) if cad_result.success else []

print(f"  Camadas dxf_core: {len(dados_estruturais.get('resumo_por_camada', {}))}")
print(f"  Itens estruturais (dxf_core): {len(dados_estruturais.get('resumo_por_camada', {}))}")
print(f"  Blocos CAD adaptados: {len(blocos_cad)}")

# ═══════════════════════════════════════════
# 3/5 - LLM MEMORIAL (DXF + descricao + NBRs)
# ═══════════════════════════════════════════
print()
print("="*60)
print("3/5 - LLM MEMORIAL (com descricao + NBRs via RAG)")
print("="*60)
print(f"  Chamando LLM (gemma4:31b-cloud)...")

metadados = {
    "nome": "Residencial Casona 228m²" if "casona" in DXF else "Planta Geminada 48,60m²",
    "localizacao": "Não informada",
    "tipo_construcao": "Residencial Unifamiliar" if "casona" in DXF else "Residencial Geminado",
    "padrao_acabamento": "Médio",
    "descricao_obra": DESCRICAO_OBRA,
}

ambientes_final = []
for idx, room in enumerate(cad_result.rooms):
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
fallback_msg = "ATIVADO: areas dos ambientes vieram dos textos TXT_AREA" if cad_result.used_text_fallback else "DESATIVADO: areas vieram do calculo geometrico"

# Contexto rico para NBR RAG: inclui descricao da obra
contexto_obra = f"{metadados['tipo_construcao']} {metadados['nome']} - {DESCRICAO_OBRA[:400]} ambientes: {', '.join(a['nome'] for a in ambientes_final)}"
system_prompt = inject_nbrs_into_prompt(SYSTEM_PROMPT_AUDITOR, contexto_obra=contexto_obra, k=5)

user_prompt = USER_PROMPT_MEMORIAL_DESCRITIVO.format(
    metadados_obra=json.dumps(metadados, ensure_ascii=False, indent=2),
    descricao_obra=DESCRICAO_OBRA,
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

qtd_nbrs = len(memorial_descritivo.get("normas_tecnicas", []))
print(f"  Ambientes: {len(memorial_descritivo.get('ambientes', []))}")
print(f"  NBRs citadas: {qtd_nbrs}")

json_path = f"pdfs/memorial_{TS}.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(memorial_descritivo, f, indent=2, ensure_ascii=False)
print(f"  JSON salvo: {json_path}")

# ═══════════════════════════════════════════
# 4/5 - PDF MEMORIAL
# ═══════════════════════════════════════════
print()
print("="*60)
print("4/5 - PDF MEMORIAL")
print("="*60)
pdf_memorial = f"pdfs/memorial_{TS}.pdf"
gerar_pdf_memorial_descritivo(
    memorial_dict=memorial_descritivo,
    metadados=metadados,
    output_path=pdf_memorial,
)
tamanho = os.path.getsize(pdf_memorial)
print(f"  PDF: {pdf_memorial} ({tamanho / 1024:.1f} KB)")

# ═══════════════════════════════════════════
# 5/5 - ORCAMENTO SINAPI
# ═══════════════════════════════════════════
print()
print("="*60)
print("5/5 - ORCAMENTO SINAPI")
print("="*60)

from apps.projetos.ai.services.adapter import adaptar_memorial_para_orcamento
from apps.projetos.ai.cad.structural_analysis import adaptar_analise_estrutural, detectar_estrutural

itens_cad = adaptar_memorial_para_orcamento(dados_estruturais)

# Analise estrutural geometrica (so ativa se houver camadas estruturais no DXF)
itens_estruturais = adaptar_analise_estrutural(memorial)
if itens_estruturais:
    tipos_estruturais = {i["type"] for i in itens_estruturais}
    itens_cad = [i for i in itens_cad if i["type"] not in tipos_estruturais]
    itens_cad.extend(itens_estruturais)
ids_existentes = {i["id"] for i in itens_cad}
for b in blocos_cad:
    if b["id"] not in ids_existentes:
        itens_cad.append(b)
        ids_existentes.add(b["id"])

sugestoes = gerar_sugestoes_orcamento(itens_cad, usar_llm=True)
orcamento = calcular_orcamento_final(sugestoes, taxa_bdi=25.0)
resumo = orcamento.get("resumo", {})

print(f"  Itens orcados: {resumo.get('total_itens', 0)}")
print(f"  Sem matching: {resumo.get('total_sem_itens', 0)}")
print(f"  Subtotal: R$ {resumo.get('subtotal', 0):.2f}")
print(f"  TOTAL: R$ {resumo.get('total_geral', 0):.2f}")

csv_path = f"csv/orcamento_{TS}.csv"
exportar_csv(sugestoes, orcamento, csv_path)
print(f"  CSV: {csv_path} ({os.path.getsize(csv_path) / 1024:.1f} KB)")

pdf_orc = f"pdfs/orcamento_{TS}.pdf"
exportar_pdf(sugestoes, orcamento, {"nome": "Orcamento SINAPI"}, pdf_orc)
print(f"  PDF: {pdf_orc} ({os.path.getsize(pdf_orc) / 1024:.1f} KB)")

# ═══════════════════════════════════════════
print()
print("="*60)
print("RESUMO FINAL")
print("="*60)
print(f"  Memorial JSON:  {json_path}")
print(f"  Memorial PDF:   {pdf_memorial}")
print(f"  Orcamento CSV:  {csv_path}")
print(f"  Orcamento PDF:  {pdf_orc}")
print(f"  Valor orcado:   R$ {resumo.get('total_geral', 0):.2f}")
if qtd_nbrs > 0:
    print()
    print(f"  NORMAS TECNICAS CITADAS NO MEMORIAL ({qtd_nbrs}):")
    for n in memorial_descritivo.get("normas_tecnicas", []):
        print(f"    - {n.get('nbr', '')}: {n.get('aplicacao', '')}")
