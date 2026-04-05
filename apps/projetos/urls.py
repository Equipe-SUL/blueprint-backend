from django.urls import path, include
from .views import UploadArquivoView, ProjetosViewSet, server_status, ItemProjetoView, TesteUploadPlanilhaView, InterpretarArquivoDxfView
from django.conf import settings
from django.conf.urls.static import static 
from rest_framework import routers


router = routers.DefaultRouter()
router.register(r'projetos', ProjetosViewSet)


urlpatterns = [
    path('', include(router.urls)),
    path('server/', server_status, name='server_status'),
    path('projetos/<int:projeto_id>/upload/', UploadArquivoView.as_view(), name='upload_arquivo'),
    path('projetos/<int:projeto_id>/itens/', ItemProjetoView.as_view(), name='itens_projeto'),
    path('projetos/<int:projeto_id>/teste-planilha/', TesteUploadPlanilhaView.as_view(), name='teste_planilha'),
    path('projetos/<int:projeto_id>/arquivos/<int:arquivo_id>/interpretar/', InterpretarArquivoDxfView.as_view(), name='interpretar_dxf'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)