from django.db import models
from django.contrib.postgres.fields import ArrayField 

class Projeto(models.Model):
    class TipoProjeto(models.TextChoices):
        ELETRICA = 'eletrica', 'Elétrica'
        HIDRAULICA = 'hidraulica', 'Hidráulica'
        ALVENARIA = 'alvenaria', 'Alvenaria'
        SPDA = 'spda', 'SPDA'
        COMBATE_A_INCENDIO = 'combate_a_incendio', 'Combate a Incêndio'

    # fk de user futuramente
    nome_obra = models.CharField(max_length=100)
    cidade_obra = models.CharField(max_length=100)
    estado_obra = models.CharField(max_length=2)
    desc_obra = models.TextField(blank=True)
    tipo_projeto = ArrayField(
        models.CharField(max_length=50, choices=TipoProjeto.choices),
        default=list,
        blank=False
    )
    taxa_bdi = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome_obra} ({self.cidade_obra}, {self.estado_obra})"
    

class ArquivoUpload(models.Model):
    class Status(models.TextChoices):
        PENDENTE   = "pendente",   "Pendente"
        PROCESSADO = "processado", "Processado"
        ERRO       = "erro",       "Erro"

    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="arquivos",
    )

    nome_original   = models.CharField(max_length=255)
    caminho_arquivo  = models.TextField()
    status_processamento = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    tamanho_mb      = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    enviado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome_original} [{self.status_processamento}]"
    
    
    
class ItemProjeto(models.Model):
    class Origem(models.TextChoices):
        SINAPI = 'sinapi', 'SINAPI'
        PROPRIO = 'proprio', 'Composição Própria'
        
    # Relacionamos o item ao Projeto e ao Arquivo que o gerou (CA.2)
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='itens')
    arquivo = models.ForeignKey(ArquivoUpload, on_delete=models.CASCADE, related_name='itens_extraidos')
    
    # Campos de dados do item (Exemplos comuns de itens de obra)
    descricao = models.TextField()
    unidade = models.CharField(max_length=20)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    
    # RN.2: Origem inicial: sinapi
    origem = models.CharField(
        max_length=50, 
        choices = Origem.choices,
        default = Origem.SINAPI)
    
    # RN.1: Status inicial: pendente
    status_mapeamento = models.CharField(max_length=20, default='pendente')

    def __str__(self):
        return f"{self.descricao[:30]}... ({self.projeto.nome_obra})"   
    

    
    