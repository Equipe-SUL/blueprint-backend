from rest_framework import serializers
from .models import Projeto, ArquivoUpload , ItemProjeto , CatalogoItem

class ProjetoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projeto
        fields = '__all__'

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
    
    
    
class ItemProjetoSerializer(serializers.ModelSerializer):
    descricao_original = serializers.CharField(source='descricao')
    
    class Meta:
        model = ItemProjeto
        fields = [
            'id', 
            'projeto', 
            'arquivo', 
            'catalogo',
            'descricao_original', 
            'unidade', 
            'quantidade', 
            'preco_unitario', 
            'origem', 
            'status_mapeamento'
        ]
        # Aqui deixamos a origem e status como somente leitura para o usuário, 
        # pois o sistema vai preencher isso via Regra de Negócio (RN.1 e RN.2)
        read_only_fields = ['origem', 'status_mapeamento']
        extra_kwargs = {
            'arquivo': {'required': False, 'allow_null': True},
            'preco_unitario': {'required': False , 'default' : '0.00'}
        }
        
        
        



