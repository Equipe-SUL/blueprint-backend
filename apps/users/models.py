from django.db import models
from django.contrib.auth.models import User # <- Importamos o usuário nativo

class PerfilMilitar(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    
    class Patentes(models.TextChoices):
        SOLDADO = 'Soldado', 'Soldado'
        CABO = 'Cabo', 'Cabo'
        TERCEIRO_SARGENTO = 'Terceiro-Sargento', 'Terceiro-Sargento'
        SEGUNDO_SARGENTO = 'Segundo-Sargento', 'Segundo-Sargento'
        PRIMEIRO_SARGENTO = 'Primeiro-Sargento', 'Primeiro-Sargento'
        SUBTENENTE = 'Subtenente', 'Subtenente'
        SEGUNDO_TENENTE = 'Segundo-Tenente', 'Segundo-Tenente'
        PRIMEIRO_TENENTE = 'Primeiro-Tenente', 'Primeiro-Tenente'
        CAPITAO = 'Capitão', 'Capitão'
        MAJOR = 'Major', 'Major'
        TENENTE_CORONEL = 'Tenente-Coronel', 'Tenente-Coronel'
        CORONEL = 'Coronel', 'Coronel'
        GEN_BRIGADA = 'General-de-Brigada', 'General-de-Brigada'
        GEN_DIVISAO = 'General-de-Divisão', 'General-de-Divisão'
        GEN_EXERCITO = 'General-de-Exército', 'General-de-Exército'

    class Unidades(models.TextChoices):
        BIL_6 = '6° Batalhão de Infantaria Leve do Exército', '6° Batalhão de Infantaria Leve do Exército'
        CMDO_12_BDA = 'Comando da 12 Brigada de Infantaria Leve Aeromovel', 'Comando da 12 Brigada de Infantaria Leve Aeromovel'

    telefone = models.CharField(max_length=20, blank=True, null=True)
    matricula = models.CharField(max_length=50, unique=True)
    patente = models.CharField(max_length=50, choices=Patentes.choices)
    unidade = models.CharField(max_length=150, choices=Unidades.choices)

    def __str__(self):
        return f"Perfil de {self.user.email} - {self.patente}"