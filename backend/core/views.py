from django.shortcuts import render
<<<<<<< HEAD
from django.contrib.auth.decorators import login_required 
from django.shortcuts import render, redirect 
from .forms import AIModelForm 
 
@login_required 
def upload_model(request): 
   if request.method == "POST": 
       form = AIModelForm(request.POST, request.FILES) 
       if form.is_valid(): 
           model = form.save(commit=False) 
           model.uploaded_by = request.user 
           model.save() 
           return redirect("model_list") 
   else: 
       form = AIModelForm() 
 
   return render(request, "upload.html", {"form": form}) 
 
=======
from .models import AIModel

>>>>>>> f10e236e334acea274c7c3249569855fa4d8259b

def home(request):
    return render(request, "home.html")


def model_list(request):
    models = AIModel.objects.order_by("-upload_date") 
    return render(request, "models.html", {"models": models})