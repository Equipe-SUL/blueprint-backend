
from django.urls import path, include 
from django.contrib import admin
from apps.projetos.views import ProjetosViewSet
from rest_framework import routers


router = routers.DefaultRouter()
router.register(r'projetos', ProjetosViewSet)



urlpatterns = [
    path('admin/', admin.site.urls), 
    path('api/', include(router.urls))
]

