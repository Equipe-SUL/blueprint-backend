"""
Management command: ingerir_referencia_sinapi
Ingere a tabela SINAPI Referência (ISD) no ChromaDB.
Uso: python manage.py ingerir_referencia_sinapi [--limpar]
"""
from django.core.management.base import BaseCommand
from apps.projetos.ai.rag.ingest_referencia import carregar_e_vetorizar_referencia, limpar_e_reingerir_tudo


class Command(BaseCommand):
    help = "Ingere a tabela SINAPI Referência (ISD) no ChromaDB"

    def add_arguments(self, parser):
        parser.add_argument('--limpar', action='store_true', help='Limpa a coleção e reingere tudo')

    def handle(self, *args, **options):
        if options['limpar']:
            self.stdout.write("Limpando e reingerindo tudo (Mão de Obra + Referência)...")
            limpar_e_reingerir_tudo()
        else:
            self.stdout.write("Ingerindo SINAPI Referência...")
            carregar_e_vetorizar_referencia()
        self.stdout.write(self.style.SUCCESS("Concluído!"))
