from django.urls import path
from . import views

urlpatterns = [
    # Rota de checagem para o app de users.
    path('status/', views.users_status, name='users_status'),
    # Aqui embaixo deve adicionar as rotas de API quando o model e as views
    # de autenticacao estiverem prontos. Exemplo:
    # path('register/', views.register, name='register'),
    # path('login/', views.login, name='login'),
    # path('logout/', views.logout, name='logout'),
]
