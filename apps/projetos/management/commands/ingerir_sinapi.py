from django.core.management.base import BaseCommand
from apps.projetos.ai.rag.documents import carregar_e_vetorizar_sinapi

class Command(BaseCommand):
    help = 'Executa a ingestão da planilha SINAPI para o banco vetorial ChromaDB'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('\n[PASSO 1] A INICIAR A CRIAÇÃO DA BASE VETORIAL (COM CÓDIGOS REAIS)...'))
        
        # Executa a vetorização lendo o arquivo de Mão de Obra (que não tem códigos zerados)
        carregar_e_vetorizar_sinapi()
        
        self.stdout.write(self.style.SUCCESS('\nMissão de Ingestão concluída com sucesso!'))