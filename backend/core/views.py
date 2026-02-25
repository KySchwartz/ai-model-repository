from django.shortcuts import render
from django.contrib.auth.decorators import login_required 
from django.shortcuts import render, redirect 
from .models import AIModel
from .forms import CustomSignupForm
from .forms import AIModelForm 
 
@login_required 
def upload_model(request): 
   if request.method == "POST": 
       form = AIModelForm(request.POST, request.FILES) 
       if form.is_valid(): 
           model = form.save(commit=False) 
           model.developer = request.user 
           model.save() 
           return redirect("model_list") 
   else: 
       form = AIModelForm() 
 
   return render(request, "upload.html", {"form": form}) 

def signup_view(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login') # Redirect to login page after success
    else:
        form = CustomSignupForm()
    return render(request, 'signup.html', {'form': form})
 
def home(request):
    return render(request, "home.html")


def model_list(request):
    models = AIModel.objects.order_by("-upload_date") 
    return render(request, "models.html", {"models": models})