from django.shortcuts import render
from django.contrib.auth.decorators import login_required 
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from .models import AIModel
from .forms import CustomSignupForm
from .forms import AIModelForm 
from .forms import AIServiceForm
from .ai_client import get_ai_status
from .ai_client import validate_model_with_ai
import httpx
from asgiref.sync import sync_to_async
from asgiref.sync import async_to_sync
import os
 
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
    service = get_object_or_404(AIModel, id=model_id, is_interactive=True)
    result = None
    download_url = None

    if request.method == "POST":
        input_data = ""
        
        # Check if the service expects a file or text
        if service.input_type == 'file' and 'user_file' in request.FILES:
            uploaded_file = request.FILES['user_file']
            # Save the incoming file to a 'temp_uploads' folder in media
            temp_path = os.path.join(settings.MEDIA_ROOT, 'temp_uploads', uploaded_file.name)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            with open(temp_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # We pass the path of the Excel file to FastAPI instead of raw text
            input_data = f"temp_uploads/{uploaded_file.name}"
        else:
            input_data = request.POST.get("user_input", "")

        # Now call FastAPI (same as before, but 'user_input' might now be a file path)
        try:
            async def call_ai_suite():
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://ai_suite:8001/execute", 
                        params={
                            "model_id": service.id, 
                            "user_input": input_data, # Could be text OR the path to the Excel
                            "file_path": service.model_file.name,
                            "output_type": service.output_type,
                            "extension": service.output_extension
                        },
                        timeout=300.0
                    )
                    return response.json()

            response_data = async_to_sync(call_ai_suite)()
            
            if response_data.get("status") == "success":
                result = response_data.get("message")
                download_url = response_data.get("download_url")
            else:
                result = f"Error: {response_data.get('message')}"
            
        except Exception as e:
            result = f"Communication Error: {str(e)}"

    return render(request, "model_service.html", {
        "service": service, 
        "result": result,
        "download_url": download_url
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
                return redirect('service_catalog')
            else:
                form.add_error(None, f"AI Validation Failed: {validation.get('message')}")
    else:
        form = AIServiceForm()
    
    return render(request, "upload_service.html", {"form": form})