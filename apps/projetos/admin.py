from django.contrib import admin
from .models import Projeto
class Projetos(admin.ModelAdmin):
    list_display = ('id', 'nome_obra', 'cidade_obra', 'estado_obra', 'taxa_bdi', 'criado_em')
    list_display_links = ('id', 'nome_obra')
    search_fields = ('nome_obra', 'cidade_obra', 'estado_obra')
    list_filter = ('estado_obra', 'criado_em')
    list_per_page = 25

admin.site.register(Projeto, Projetos)