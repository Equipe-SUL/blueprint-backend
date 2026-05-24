"""
Management command: ingerir_nbrs
Ingere os PDFs de NBRs no ChromaDB (colecao nbrs_collection).
Uso: python manage.py ingerir_nbrs
"""
from django.core.management.base import BaseCommand
from apps.projetos.ai.rag.ingest_nbrs import ingerir_nbrs


class Command(BaseCommand):
    help = "Ingere os PDFs de NBRs no ChromaDB"

    def handle(self, *args, **options):
        self.stdout.write("Ingerindo NBRs...")
        ingerir_nbrs()
        self.stdout.write(self.style.SUCCESS("NBRs indexadas com sucesso!"))
