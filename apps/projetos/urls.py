from django.urls import path
from .views import UploadArquivoView, server_status
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('server', server_status, name='server_status'),
    path('projetos/<int:projeto_id>/upload/', UploadArquivoView.as_view(), name='upload_arquivo'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)