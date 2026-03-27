from django.urls import path, include
from .views import UploadArquivoView, ProjetosViewSet, server_status , ItemProjetoView
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
    
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)