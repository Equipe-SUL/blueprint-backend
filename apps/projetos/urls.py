from django.urls import path, include
from .views import UploadArquivoView, ProjetosViewSet, server_status, ItemProjetoView, TesteUploadPlanilhaView, RetomarPipelineView, ProcessarArquivoView, ServirMemorialPDFView, GerarOrcamentoView, ServirOrcamentoPDFView
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
    path('projetos/<int:projeto_id>/retomar/', RetomarPipelineView.as_view(), name='retomar_pipeline'),
    path('projetos/<int:projeto_id>/upload/<int:arquivo_id>/', UploadArquivoView.as_view(), name='delete_arquivo_upload'),
    path('projetos/<int:projeto_id>/processar/<int:arquivo_id>/', ProcessarArquivoView.as_view(), name='processar_arquivo'),
    path('projetos/<int:projeto_id>/memorial/<int:memorial_id>/pdf/', ServirMemorialPDFView.as_view(), name='servir_memorial_pdf'),
    path('projetos/<int:projeto_id>/gerar-orcamento/<int:arquivo_id>/', GerarOrcamentoView.as_view(), name='gerar_orcamento'),
    path('projetos/<int:projeto_id>/orcamento/<int:memorial_id>/pdf/', ServirOrcamentoPDFView.as_view(), name='servir_orcamento_pdf'),
    path('projetos/<int:projeto_id>/teste-planilha/', TesteUploadPlanilhaView.as_view(), name='teste_planilha'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)