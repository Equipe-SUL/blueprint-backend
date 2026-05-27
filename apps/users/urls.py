from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegistroView

urlpatterns = [
    # Rota de checagem para o app de users.
    path('status/', views.users_status, name='users_status'),
    # Aqui embaixo deve adicionar as rotas de API quando o model e as views
    # de autenticacao estiverem prontos. Exemplo:
    path('cadastro/', RegistroView.as_view(), name='cadastro'),
    path('login/', TokenObtainPairView.as_view(), name='login'), # Esta é a rota que verifica a senha e gera o Token!
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # path('logout/', views.logout, name='logout'),
]
