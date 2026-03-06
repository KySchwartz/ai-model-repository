from django.shortcuts import render
from django.contrib.auth.decorators import login_required 
from django.shortcuts import render, redirect, get_object_or_404
from .models import AIModel
from .forms import CustomSignupForm
from .forms import AIModelForm 
from .forms import AIServiceForm
from .ai_client import get_ai_status
from .ai_client import validate_model_with_ai
import httpx
from asgiref.sync import sync_to_async
from asgiref.sync import async_to_sync
 
@login_required 
async def upload_model(request):
    if request.method == "POST":
        form = AIModelForm(request.POST, request.FILES)
        if form.is_valid():
            # 1. Temporarily hold the data
            model_instance = form.save(commit=False)
            
            # 2. Call AI Suite for validation
            validation = await validate_model_with_ai(
                model_instance.framework, 
                model_instance.version, 
                request.FILES['file_path'].name
            )
            
            # 3. Handle results
            if validation.get("status") == "valid":
                model_instance.developer = request.user
                model_instance.save()
                return redirect('model_list')
            else:
                form.add_error(None, f"AI Validation Failed: {validation.get('message')}")
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

# Code for just displaying the homepage without async functionality
#def home(request):
#    return render(request, "home.html")

# View for code repository
def model_list(request):
    models = AIModel.objects.filter(is_interactive=False).order_by("-upload_date") 
    return render(request, "models.html", {"models": models})

# View for AI Services
def ai_service_catalog(request):
    # Only fetch models that are marked as interactive services
    services = AIModel.objects.filter(is_interactive=True).order_by('-upload_date')
    return render(request, "service_catalog.html", {"services": services})

# View to retrieve AI service interfaces
def model_service_page(request, model_id):
    # Fetch the model metadata from the database
    service = get_object_or_404(AIModel, id=model_id, is_interactive=True)
    result = None

    if request.method == "POST":
        # 1. Prepare the data to send to FastAPI
        # We send the model_id and the relative path of the file saved in /media/ 
        execution_payload = {
            "model_id": service.id,
            "file_path": service.model_file.name # e.g., 'models/my_model.txt'
        }

        # 2. Call the FastAPI 'execute' endpoint
        try:
            async def call_fastapi():
                async with httpx.AsyncClient() as client:
                    # Pointing to the execute endpoint we created in main.py
                    response = await client.post(
                        "http://ai_suite:8001/execute", 
                        params=execution_payload, # FastAPI expects these as query params
                        timeout=10.0
                    )
                    return response.json()

            # Execute the async call within our sync view
            response_data = async_to_sync(call_fastapi)()
            result = response_data.get("message") # This will be the "Success" message from FastAPI 
            
        except Exception as e:
            result = f"Execution Error: {str(e)}"

    return render(request, "model_service.html", {
        "service": service,
        "result": result
    })

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

@login_required
def upload_service(request):  # Changed from 'async def' to 'def'
    if request.method == "POST":
        form = AIServiceForm(request.POST, request.FILES)
        if form.is_valid():
            model_instance = form.save(commit=False)
            model_instance.developer = request.user
            model_instance.is_interactive = True 
            
            # Use async_to_sync to wrap the FastAPI call only
            # This allows the rest of the view to stay synchronous and safe for base.html
            validation = async_to_sync(validate_model_with_ai)(
                model_instance.framework, 
                model_instance.version, 
                request.FILES['model_file'].name
            )
            print(f"DEBUG: FastAPI responded with: {validation}", flush=True)
            
            if validation.get("status") == "valid":
                model_instance.save()
                return redirect('model_list')
            else:
                form.add_error(None, f"AI Validation Failed: {validation.get('message')}")
    else:
        form = AIServiceForm()
    
    return render(request, "upload_service.html", {"form": form})