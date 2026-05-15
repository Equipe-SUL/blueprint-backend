from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import routers

from .views.projetos import ProjetosViewSet
from .views.upload import UploadArquivoView, RetomarPipelineView
from .views.itens import ItemProjetoView, TesteUploadPlanilhaView, InterpretarArquivoDxfView
from .views.server import server_status

router = routers.DefaultRouter()
router.register(r'projetos', ProjetosViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('server/', server_status, name='server_status'),
    path('projetos/<int:projeto_id>/upload/', UploadArquivoView.as_view(), name='upload_arquivo'),
    path('projetos/<int:projeto_id>/retomar/', RetomarPipelineView.as_view(), name='retomar_pipeline'),
    path('projetos/<int:projeto_id>/itens/', ItemProjetoView.as_view(), name='itens_projeto'),
    path('projetos/<int:projeto_id>/teste-planilha/', TesteUploadPlanilhaView.as_view(), name='teste_planilha'),
    path('projetos/<int:projeto_id>/interpretar-dxf/', InterpretarArquivoDxfView.as_view(), name='interpretar_dxf'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
