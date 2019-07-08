from django.shortcuts import render


# Create your views here.
def proxy_manager(request):
    return render(request, "manage.html")
