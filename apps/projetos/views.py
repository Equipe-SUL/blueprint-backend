
from django.http import HttpResponse

# Create your views here.
def server_status(request):
    return HttpResponse("Servidor está ativo")

