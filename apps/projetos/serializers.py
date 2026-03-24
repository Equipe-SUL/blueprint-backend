from rest_framework import serializers
from .models import Projeto, ArquivoUpload

# class ProjetoSerializer(serializers.ModelSerializer):

class UploadArquivoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArquivoUpload
        fields = [
            "id",
            "projeto",
            "nome_original",
            "caminho_arquivo",
            "status_processamento",
            "tamanho_mb",
            "enviado_em",
        ]
        read_only_fields = fields
    


