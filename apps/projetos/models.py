from django.db import models

class Projeto(models.Model):
    # fk de user futuramente
    nome_obra = models.CharField(max_length=100)
    cidade_obra = models.CharField(max_length=100)
    estado_obra = models.CharField(max_length=2)
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
    
    