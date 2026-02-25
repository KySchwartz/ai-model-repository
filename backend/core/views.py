from django.shortcuts import render
from .models import AIModel


def home(request):
    return render(request, "home.html")


def model_list(request):
    models = AIModel.objects.order_by("-upload_date") 
    return render(request, "models.html", {"models": models})