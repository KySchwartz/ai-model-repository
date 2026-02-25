from django.shortcuts import render
from django.contrib.auth.decorators import login_required 
from django.shortcuts import render, redirect 
from .models import AIModel
from .forms import CustomSignupForm
from .forms import AIModelForm 
from .ai_client import get_ai_status
import httpx
from asgiref.sync import sync_to_async
 
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

#def home(request):
#    return render(request, "home.html")


def model_list(request):
    models = AIModel.objects.order_by("-upload_date") 
    return render(request, "models.html", {"models": models})

async def home(request):
    # 1. Resolve Sync Database logic before rendering
    # We check if user is auth and get their username/role safely
    is_auth = await sync_to_async(lambda: request.user.is_authenticated)()
    user_name = await sync_to_async(lambda: request.user.username if is_auth else None)()
    user_role = await sync_to_async(lambda: request.user.role if is_auth else None)()

    # 2. Call the AI Suite Microservice
    ai_status = "Offline"
    try:
        async with httpx.AsyncClient() as client:
            # We use the service name 'ai_suite' defined in docker-compose
            response = await client.get("http://ai_suite:8001/status", timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                ai_status = f"Online (v{data['version']})"
    except Exception:
        ai_status = "Connection Failed"

    return render(request, "home.html", {
        "is_auth": is_auth,
        "user_name": user_name,
        "user_role": user_role,
        "ai_status": ai_status
    })