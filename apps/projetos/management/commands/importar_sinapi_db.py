import os
import pandas as pd
from django.core.management.base import BaseCommand
from django.conf import settings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

CHROMA_PERSIST_DIR = os.path.join(settings.BASE_DIR, "chroma_db")

class Command(BaseCommand):
    help = 'Popula o ChromaDB com os dados da matriz Nacional da SINAPI.'

    def add_arguments(self, parser):
        parser.add_argument('caminho_xlsx', type=str, help='Caminho para o arquivo XLSX')
        parser.add_argument('--sheet', type=str, required=True, help='Nome da aba (ex: ISD, CSD)')
        parser.add_argument('--tipo', type=str, choices=['insumo', 'composicao'], required=True, help='Define se é Insumo ou Composição')

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
        coluna_preco_sp = -1
        
        for index, row in df.head(15).iterrows():
            valores = [str(x).strip().upper() for x in row.values]
            if 'SP' in valores and 'RJ' in valores and 'MG' in valores:
                linha_cabecalho = index
                coluna_preco_sp = valores.index('SP')
                break

        if linha_cabecalho == -1:
            self.stdout.write(self.style.ERROR("❌ Não foi possível encontrar as colunas de estados (SP, RJ) no cabeçalho."))
            return

        self.stdout.write(self.style.SUCCESS(f"Cabeçalho encontrado na linha {linha_cabecalho + 1}. Mapeando preços para o estado de São Paulo (SP)."))

        documentos = []
        linhas_ignoradas = 0

        # Fatiamos a planilha para começar exatamente abaixo da linha dos estados
        df_dados = df.iloc[linha_cabecalho + 1:]

        for _, row in df_dados.iterrows():
            # Acessamos por posição da coluna: 0=Código, 1=Descrição, 2=Unidade
            descricao = str(row.values[1]).strip()
            
            # Se não tem descrição, é linha vazia ou rodapé da Caixa
            if pd.isna(row.values[1]) or not descricao or descricao.lower() == 'nan':
                linhas_ignoradas += 1
                continue

            codigo = str(row.values[0]).strip()
            unidade = str(row.values[2]).strip()
            
            # Puxamos o preço indexando diretamente na coluna de SP
            preco = self.limpar_preco(row.values[coluna_preco_sp])

            conteudo_semantico = f"SINAPI {codigo} - {descricao}. Preço: R${preco:.2f} por {unidade}."

            doc = Document(
                page_content=conteudo_semantico,
                metadata={
                    "origem": "sinapi",
                    "tipo": tipo_arquivo,
                    "codigo": codigo,
                    "preco": preco,
                    "unidade": unidade,
                    "disciplina": "geral"
                }
            )
            documentos.append(doc)

        self.stdout.write(self.style.SUCCESS(f"Preparados {len(documentos)} itens válidos. (Ignoradas {linhas_ignoradas} linhas)."))

        tamanho_lote = 1000
        total_lotes = (len(documentos) // tamanho_lote) + 1

        self.stdout.write(self.style.WARNING("Iniciando inserção no ChromaDB..."))
        
        for i in range(0, len(documentos), tamanho_lote):
            lote = documentos[i : i + tamanho_lote]
            vector_store.add_documents(lote)
            self.stdout.write(f"✅ Lote {(i//tamanho_lote) + 1}/{total_lotes} persistido.")

        self.stdout.write(self.style.SUCCESS(f"🚀 Sucesso! Banco SINAPI populado em '{CHROMA_PERSIST_DIR}'."))