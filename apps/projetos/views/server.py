from django.http import HttpResponse


def server_status(request):
    return HttpResponse("Servidor está ativo")
