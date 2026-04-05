import json
import os
import re
import shutil
import unicodedata

import pandas as pd
from django.core.management.base import BaseCommand
from django.conf import settings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

CHROMA_PERSIST_DIR = os.path.join(settings.BASE_DIR, "chroma_db")
GRUPOS_JSON_PATH = os.path.join(CHROMA_PERSIST_DIR, "sinapi_grupos.json")

_UFS_BR = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
    "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}


def _norm_str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _slugify(texto: str) -> str:
    s = _norm_str(texto).lower()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _is_codigo_sinapi(v) -> bool:
    s = _norm_str(v)
    if not s:
        return False
    s = re.sub(r"\D", "", s)
    return len(s) >= 4


def _inferir_disciplina(grupo: str, descricao: str) -> str:
    t = f"{_norm_str(grupo)} {_norm_str(descricao)}".lower()
    if any(k in t for k in [
        "tubo", "tubos", "esgoto", "hidraul", "hidross", "sanit", "bomba", "registro", "valvula",
        "ralo", "lavat", "vaso", "pia", "caixa d", "caixa de", "chuve", "torne",
    ]):
        return "hidraulica"
    if any(k in t for k in [
        "eletric", "eletro", "cabos", "cabo", "fio", "disjunt", "quadro", "lumin", "tomada",
        "interrupt", "aterr", "spda",
    ]):
        return "eletrica"
    if any(k in t for k in ["alven", "tijolo", "argamassa", "reboco", "parede", "bloco"]):
        return "alvenaria"
    if any(k in t for k in ["incend", "hidrante", "sprink", "extint", "mangot"]):
        return "combate_a_incendio"
    return "geral"


def _salvar_grupos_json(grupos: list[dict]) -> None:
    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
    with open(GRUPOS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"grupos": grupos}, f, ensure_ascii=False, indent=2)


def _carregar_grupos_json_existente() -> list[dict]:
    if not os.path.exists(GRUPOS_JSON_PATH):
        return []
    try:
        with open(GRUPOS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        grupos = data.get("grupos")
        return grupos if isinstance(grupos, list) else []
    except Exception:
        return []


def _extrair_grupos_da_aba_csd(caminho_absoluto: str, sheet: str) -> list[dict]:
    """Extrai uma lista de grupos (nome/slug) da aba CSD.

    A planilha pode ter ou não cabeçalho. Tentamos localizar a coluna que contém 'GRUPO'.
    """
    try:
        df = pd.read_excel(caminho_absoluto, sheet_name=sheet, header=None)
    except Exception:
        return []

    col_grupo = 0
    linha_inicio = 0

    for idx, row in df.head(30).iterrows():
        vals = [_norm_str(x).upper() for x in row.values]
        for j, v in enumerate(vals):
            if v in {"GRUPO", "GRUPOS"}:
                col_grupo = j
                linha_inicio = idx + 1
                break
        if linha_inicio:
            break

    grupos: dict[str, dict] = {}
    for _, row in df.iloc[linha_inicio:].iterrows():
        nome = _norm_str(row.values[col_grupo] if col_grupo < len(row.values) else None)
        if not nome:
            continue
        if nome.upper() in {"TOTAL", "SUBTOTAL"}:
            continue
        slug = _slugify(nome)
        if not slug:
            continue
        if slug not in grupos:
            grupos[slug] = {"nome": nome, "slug": slug, "disciplina": _inferir_disciplina(nome, "")}

    return list(grupos.values())

class Command(BaseCommand):
    help = 'Popula o ChromaDB com os dados da matriz Nacional da SINAPI.'

    def add_arguments(self, parser):
        parser.add_argument('caminho_xlsx', type=str, help='Caminho para o arquivo XLSX')
        parser.add_argument('--sheet', type=str, required=True, help='Nome da aba (ex: ISD, CSD)')
        parser.add_argument('--tipo', type=str, choices=['insumo', 'composicao'], required=True, help='Define se é Insumo ou Composição')
        parser.add_argument('--uf', type=str, default='SP', help='UF para precificação (padrão: SP)')
        parser.add_argument('--reset', action='store_true', help='Apaga o diretório chroma_db antes de importar')
        parser.add_argument(
            '--grupos',
            type=str,
            default='',
            help='Lista (separada por vírgula) de grupos permitidos (nome ou slug) para importar; vazio = todos',
        )
        parser.add_argument(
            '--salvar-grupos',
            action='store_true',
            help='Gera/atualiza o arquivo chroma_db/sinapi_grupos.json com os grupos encontrados na importação',
        )
        parser.add_argument(
            '--csd-sheet',
            type=str,
            default='',
            help='Nome da aba com lista de grupos (ex: CSD) para mesclar no sinapi_grupos.json',
        )

    def limpar_preco(self, valor) -> float:
        if pd.isna(valor): 
            return 0.0
        if isinstance(valor, (int, float)): 
            return float(valor)
        
        valor_str = str(valor).strip()
        if not valor_str or valor_str == '-': 
            return 0.0
            
        if ',' in valor_str:
            valor_str = valor_str.replace('.', '').replace(',', '.')
            
        try:
            return float(valor_str)
        except ValueError:
            return 0.0

    def handle(self, *args, **options):
        caminho_xlsx = options['caminho_xlsx']
        tipo_arquivo = options['tipo']
        uf = (options.get('uf') or 'SP').strip().upper()
        if uf not in _UFS_BR:
            self.stdout.write(self.style.ERROR(f"❌ UF inválida: '{uf}'. Use uma UF do Brasil (ex: SP, RJ, MG)."))
            return

        if options.get('reset'):
            try:
                if os.path.isdir(CHROMA_PERSIST_DIR):
                    shutil.rmtree(CHROMA_PERSIST_DIR)
                    self.stdout.write(self.style.WARNING(f"🧹 Reset: removido '{CHROMA_PERSIST_DIR}'."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Falha ao resetar '{CHROMA_PERSIST_DIR}': {e}"))
                return

        caminho_absoluto = os.path.join(settings.BASE_DIR, caminho_xlsx)

        if not os.path.exists(caminho_absoluto):
            self.stdout.write(self.style.ERROR(f"❌ Arquivo não encontrado: {caminho_absoluto}"))
            return

        self.stdout.write(self.style.WARNING("Carregando modelo de Embeddings..."))
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        vector_store = Chroma(
            collection_name="base_sinapi",
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR
        )

        self.stdout.write(self.style.WARNING(f"Lendo '{caminho_absoluto}' (Aba: {options['sheet']})..."))
        
        try:
            # Lemos sem cabeçalho para varrer as linhas manualmente e ignorar a formatação da Caixa
            df = pd.read_excel(caminho_absoluto, sheet_name=options['sheet'], header=None)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro na leitura do XLSX: {e}"))
            return

        # Varredura inteligente para encontrar a linha dos estados
        linha_cabecalho = -1
        coluna_preco_uf = -1

        for index, row in df.head(40).iterrows():
            valores = [_norm_str(x).upper() for x in row.values]
            ufs_presentes = [v for v in valores if v in _UFS_BR]
            if uf in valores and len(set(ufs_presentes)) >= 5:
                linha_cabecalho = index
                coluna_preco_uf = valores.index(uf)
                break

        if linha_cabecalho == -1:
            self.stdout.write(self.style.ERROR(
                f"❌ Não foi possível encontrar o cabeçalho de UFs contendo '{uf}'. "
                "Verifique se a aba é a de custos (com colunas SP/RJ/MG...)."
            ))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Cabeçalho de UFs encontrado na linha {linha_cabecalho + 1}. "
                f"Mapeando preços para UF={uf}."
            )
        )

        documentos = []
        linhas_ignoradas = 0

        grupos_permitidos_raw = (options.get("grupos") or "").strip()
        grupos_permitidos: set[str] = set()
        if grupos_permitidos_raw:
            for g in grupos_permitidos_raw.split(","):
                g = g.strip()
                if not g:
                    continue
                grupos_permitidos.add(_slugify(g) or g.lower())

        grupos_encontrados: dict[str, dict] = {}

        csd_sheet = (options.get("csd_sheet") or "").strip()
        grupos_csd: list[dict] = []
        if csd_sheet:
            grupos_csd = _extrair_grupos_da_aba_csd(caminho_absoluto, csd_sheet)
            if grupos_csd:
                self.stdout.write(self.style.SUCCESS(f"✅ Extraídos {len(grupos_csd)} grupos da aba '{csd_sheet}'."))
            else:
                self.stdout.write(self.style.WARNING(f"⚠️ Não foi possível extrair grupos da aba '{csd_sheet}'."))

        # Fatiamos a planilha para começar exatamente abaixo da linha dos estados
        df_dados = df.iloc[linha_cabecalho + 1:]

        # Detecta layout (com ou sem coluna de grupo) olhando as primeiras linhas úteis.
        layout = None  # 'com_grupo' | 'sem_grupo'
        for _, row in df_dados.head(200).iterrows():
            valores = list(row.values)
            if len(valores) < 4:
                continue
            # layout com grupo: [grupo, codigo, descricao, unidade, ...]
            if _is_codigo_sinapi(valores[1]) and _norm_str(valores[2]) and _norm_str(valores[3]):
                layout = "com_grupo"
                break
            # layout sem grupo: [codigo, descricao, unidade, ...]
            if _is_codigo_sinapi(valores[0]) and _norm_str(valores[1]) and _norm_str(valores[2]):
                layout = "sem_grupo"
                break

        if layout is None:
            self.stdout.write(self.style.ERROR(
                "❌ Não foi possível detectar o layout da aba. Esperado: "
                "[codigo, descricao, unidade] ou [grupo, codigo, descricao, unidade]."
            ))
            return

        self.stdout.write(self.style.WARNING(f"Layout detectado: {layout}."))

        for _, row in df_dados.iterrows():
            valores = list(row.values)
            if layout == "com_grupo":
                grupo = _norm_str(valores[0])
                codigo = _norm_str(valores[1])
                descricao = _norm_str(valores[2])
                unidade = _norm_str(valores[3])
            else:
                grupo = ""
                codigo = _norm_str(valores[0])
                descricao = _norm_str(valores[1])
                unidade = _norm_str(valores[2])

            # Se não tem descrição, é linha vazia/rodapé
            if not descricao:
                linhas_ignoradas += 1
                continue

            # Se não tem código válido, ignora
            if not _is_codigo_sinapi(codigo):
                linhas_ignoradas += 1
                continue

            codigo_num = re.sub(r"\D", "", codigo)
            grupo_slug = _slugify(grupo)
            if grupos_permitidos and grupo_slug and grupo_slug not in grupos_permitidos:
                linhas_ignoradas += 1
                continue
            if grupos_permitidos and not grupo_slug:
                # se usuário restringiu grupos e a linha não tem grupo, ignoramos
                linhas_ignoradas += 1
                continue

            # Puxamos o preço indexando diretamente na coluna da UF selecionada
            preco = self.limpar_preco(valores[coluna_preco_uf] if coluna_preco_uf < len(valores) else None)

            disciplina = _inferir_disciplina(grupo, descricao)

            conteudo_partes = [f"SINAPI {codigo_num} - {descricao}."]
            if unidade:
                conteudo_partes.append(f"Unidade: {unidade}.")
            if grupo:
                conteudo_partes.append(f"Grupo: {grupo}.")
            conteudo_partes.append(f"Preço ({uf}): R${preco:.2f}.")
            conteudo_semantico = " ".join(conteudo_partes)

            doc = Document(
                page_content=conteudo_semantico,
                metadata={
                    "origem": "sinapi",
                    "tipo": tipo_arquivo,
                    "codigo": codigo_num,
                    "preco": preco,
                    "unidade": unidade,
                    "uf": uf,
                    "grupo": grupo,
                    "grupo_slug": grupo_slug,
                    "disciplina": disciplina,
                    "sheet": options["sheet"],
                },
            )
            documentos.append(doc)

            if grupo:
                key = grupo_slug or grupo
                if key not in grupos_encontrados:
                    grupos_encontrados[key] = {
                        "nome": grupo,
                        "slug": grupo_slug,
                        "disciplina": disciplina,
                    }

        self.stdout.write(self.style.SUCCESS(f"Preparados {len(documentos)} itens válidos. (Ignoradas {linhas_ignoradas} linhas)."))

        if options.get("salvar_grupos"):
            existentes = _carregar_grupos_json_existente()
            por_slug: dict[str, dict] = {}
            for g in existentes:
                slug = _norm_str(g.get("slug"))
                nome = _norm_str(g.get("nome"))
                chave = slug or _slugify(nome) or nome
                if chave:
                    por_slug[chave] = g
            for g in grupos_csd:
                slug = _norm_str(g.get("slug"))
                nome = _norm_str(g.get("nome"))
                chave = slug or _slugify(nome) or nome
                if chave:
                    por_slug[chave] = g
            for chave, g in grupos_encontrados.items():
                por_slug[chave] = g
            grupos_final = sorted(
                por_slug.values(),
                key=lambda x: (_norm_str(x.get("nome")).lower() or _norm_str(x.get("slug"))),
            )
            try:
                _salvar_grupos_json(grupos_final)
                self.stdout.write(self.style.SUCCESS(f"✅ Grupos salvos em '{GRUPOS_JSON_PATH}' ({len(grupos_final)})."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Falha ao salvar '{GRUPOS_JSON_PATH}': {e}"))

        tamanho_lote = 1000
        total_lotes = (len(documentos) // tamanho_lote) + 1

        self.stdout.write(self.style.WARNING("Iniciando inserção no ChromaDB..."))
        
        for i in range(0, len(documentos), tamanho_lote):
            lote = documentos[i : i + tamanho_lote]
            vector_store.add_documents(lote)
            self.stdout.write(f"✅ Lote {(i//tamanho_lote) + 1}/{total_lotes} persistido.")

        self.stdout.write(self.style.SUCCESS(f"🚀 Sucesso! Banco SINAPI populado em '{CHROMA_PERSIST_DIR}'."))