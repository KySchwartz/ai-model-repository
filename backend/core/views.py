from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.db.models import Q
from .models import AIModel, ModelUsage
from .forms import CustomSignupForm
from .forms import AIModelForm 
from .forms import AIServiceForm
from .ai_client import get_ai_status
from .ai_client import validate_model_with_ai
from django.utils import timezone
from datetime import timedelta
import httpx
from asgiref.sync import sync_to_async
from asgiref.sync import async_to_sync
import os
import time
import ast
import zipfile
import io
import uuid

def developer_check(user):
    """Check if the user has Developer or Admin privileges."""
    return user.is_authenticated and (user.role in ['developer', 'admin'] or user.is_superuser)

def validate_contract_in_zip(zip_file, input_type="text"):
    try:
        with zipfile.ZipFile(zip_file, 'r') as z:
            py_files = [f for f in z.namelist() if f.endswith('.py') and not f.startswith('__MACOSX')]

            if not py_files:
                return False, "No Python files found.", "Ensure your ZIP contains at least one .py file."

            # Find any main.py file anywhere in the ZIP
            main_candidates = [f for f in py_files if f.endswith("main.py")]
            entry_point = main_candidates[0] if main_candidates else py_files[0]

            with z.open(entry_point) as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == 'handle_request':
                    return True, None, None

            # If we're here, handle_request is missing
            hint = (
                "Add this to your code:\n\n"
                "def handle_request(user_input):\n"
                "    # Your logic here\n"
                "    return 'Result'"
            )
            return False, f"Missing 'handle_request' in {entry_point}", hint

    except Exception as e:
        return False, "Analysis Error", str(e)

def validate_contract_in_py(py_file):
    """Statically inspects a single .py file for handle_request."""
    try:
        content = py_file.read()
        py_file.seek(0)  # Reset pointer for saving later
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'handle_request':
                return True, None, None
        
        hint = "Add this to your code:\n\ndef handle_request(user_input):\n    return 'Result'"
        return False, "Missing 'handle_request' function.", hint
    except Exception as e:
        return False, "Python Syntax Error", str(e)

@user_passes_test(developer_check)
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

# Handles user signup
def signup_view(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login') # Redirect to login page after success
    else:
        form = CustomSignupForm()
    return render(request, 'signup.html', {'form': form})

# View for code repository
def model_list(request):
    models = AIModel.objects.filter(is_interactive=False).order_by("-upload_date") 
    return render(request, "models.html", {"models": models})

# View for AI Services
def ai_service_catalog(request):
    query = request.GET.get('q', '')
    
    if request.user.is_authenticated:
        # Admins see everything. Developers see published models OR their own unpublished ones.
        if request.user.role == 'admin' or request.user.is_superuser:
            services = AIModel.objects.filter(is_interactive=True)
        else:
            services = AIModel.objects.filter(is_interactive=True).filter(Q(is_published=True) | Q(developer=request.user))
    else:
        # Anonymous users only see published
        services = AIModel.objects.filter(is_interactive=True, is_published=True).order_by('-upload_date')

    services = services.order_by('-upload_date')

    if query:
        services = services.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(framework__icontains=query)
        )

    return render(request, "service_catalog.html", {"services": services, "query": query})

# View to retrieve AI service interfaces
def model_service_page(request, model_id):
    service = get_object_or_404(AIModel, id=model_id, is_interactive=True)
    result = None
    download_url = None
    response_data = None
    credit_error = False

    # Permission check for unpublished services
    is_admin = request.user.is_authenticated and (request.user.is_superuser or request.user.role == 'admin')
    is_dev_of_model = request.user.is_authenticated and service.developer == request.user
    if not service.is_published and not (is_admin or is_dev_of_model):
        return redirect('service_catalog')

    # Logic for managing user credits (monetization demo)
    if request.user.is_authenticated:
        now = timezone.now()
        
        # Check if subscription has expired
        if request.user.is_subscribed and request.user.subscription_expiry:
            if now > request.user.subscription_expiry:
                request.user.is_subscribed = False
                request.user.save()

        if (now - request.user.last_credit_refresh).total_seconds() >= 86400:
            # Reset total balance to Purchased + 5 (replenishing allowance without stacking)
            request.user.credit_balance = request.user.purchased_credits + 5
            request.user.last_credit_refresh = now
            request.user.save()

    if request.method == "POST":
        # Check if the user has the credit to run a model
        can_run = False
        if not request.user.is_authenticated:
            return redirect('login')
            
        # Determine if user is exempt from credit limits
        
        if is_admin or request.user.is_subscribed or is_dev_of_model:
            can_run = True
        elif request.user.credit_balance > 0:
            can_run = True
        
        if not can_run:
            return render(request, "model_service.html", {
                "service": service,
                "result": "You have run out of credits.",
                "credit_error": True
            })

        start_time = time.time()
        input_data = ""
        
        # Check if the service expects a file or text
        if service.input_type == 'file' and 'user_file' in request.FILES:
            uploaded_file = request.FILES['user_file']
            unique_filename = f"{uuid.uuid4().hex}_{uploaded_file.name}"
            # Save the incoming file to a 'temp_uploads' folder in media
            temp_path = os.path.join(settings.MEDIA_ROOT, 'temp_uploads', unique_filename)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            with open(temp_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # We pass the path of the Excel file to FastAPI instead of raw text
            input_data = f"temp_uploads/{unique_filename}"
        else:
            input_data = request.POST.get("user_input", "")

        # Now call FastAPI (same as before, but 'user_input' might now be a file path)
        try:
            async def call_ai_suite():
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://ai_suite:8001/execute", 
                        json={
                            "model_id": service.id, 
                            "user_input": input_data, # Could be text OR the path to the Excel
                            "file_path": service.model_file.name,
                            "output_type": service.output_type,
                            "extension": service.output_extension or ""
                        },
                        timeout=300.0
                    )
                    # Check for non-200 status codes to prevent JSON decode errors
                    if response.status_code != 200:
                         return {"status": "error", "message": f"Server Error ({response.status_code}): {response.text[:200]}"}
                    return response.json()

            response_data = async_to_sync(call_ai_suite)()
            
            if response_data.get("status") == "success":
                result = response_data.get("message")
                download_url = response_data.get("download_url")
                
                # Added logic for credit manipulation
                # Deduct credit on successful run (if not exempt)
                if not (request.user.is_superuser or request.user.is_subscribed or service.developer == request.user):
                    request.user.credit_balance -= 1
                    # If total balance drops below purchased amount, update the purchased anchor
                    if request.user.credit_balance < request.user.purchased_credits:
                        request.user.purchased_credits = request.user.credit_balance
                    request.user.save()
            else:
                result = f"Error: {response_data.get('message')}"
            
            # Record Telemetry
            m = response_data.get("metrics", {})
            ModelUsage.objects.create(
                model=service,
                user=request.user if request.user.is_authenticated else None,
                init_time_seconds=m.get("init_time", 0),
                execution_time_seconds=m.get("execution_time", 0),
                peak_memory_mb=m.get("peak_memory", 0),
                cpu_usage_seconds=m.get("cpu_usage", 0),
                input_size_bytes=m.get("input_size", 0),
                output_token_count=m.get("output_tokens", 0),
                output_type=service.output_type,
                error_code=m.get("error_code", "UNKNOWN"),
                status=response_data.get("status", "error")
            )
            
        except Exception as e:
            error_detail = response_data.get('message') if response_data else None
            result = f"Communication Error: {str(e)}"

    return render(request, "model_service.html", {
        "service": service, 
        "result": result,
        "error_detail": error_detail if 'error_detail' in locals() else None,
        "download_url": download_url
        })

# View for account management page
@login_required
def account_management(request):
    return render(request, "account_management.html", {
        "user": request.user,
        "days_until_refresh": 1 - (timezone.now() - request.user.last_credit_refresh).days
    })

# View for checkout page
@login_required
def checkout_view(request):
    if request.method == "POST":
        purchase_type = request.POST.get("purchase_type", "credits")
        
        if purchase_type == "subscription":
            amount = 1
            price = 11.99
            display_name = "Monthly Premium Subscription (Unlimited Usage)"
        else:
            amount = int(request.POST.get("credit_amount", 50))
            price = amount * 0.10
            display_name = f"{amount} AI Service Credits"
            
        return render(request, "checkout.html", {
            "amount": amount,
            "price": f"{price:.2f}",
            "purchase_type": purchase_type,
            "display_name": display_name
        })
    return redirect("account_management")

@login_required
def process_payment(request):
    if request.method == "POST":
        amount = int(request.POST.get("amount", 0))
        purchase_type = request.POST.get("purchase_type")

        if purchase_type == "subscription":
            request.user.is_subscribed = True
            request.user.subscription_expiry = timezone.now() + timedelta(days=30)
            request.user.save()
            messages.success(request, "Your Premium Subscription is now active for 30 days!")
        elif amount > 0:
            request.user.purchased_credits += amount
            request.user.credit_balance += amount
            request.user.save()
            messages.success(request, f"Successfully purchased {amount} credits!")
            return redirect("account_management")
    
    return redirect("account_management")

@user_passes_test(developer_check)
def toggle_publish_status(request, model_id):
    # Allow admins to toggle any service, but restrict developers to their own
    if request.user.is_superuser or request.user.role == 'admin':
        service = get_object_or_404(AIModel, id=model_id)
    else:
        service = get_object_or_404(AIModel, id=model_id, developer=request.user)

    service.is_published = not service.is_published
    service.save()
    status = "published" if service.is_published else "hidden"
    messages.success(request, f"Service '{service.title}' is now {status}.")
    
    # Redirect back to the referring page (e.g., catalog or dashboard) for better UX
    return redirect(request.META.get('HTTP_REFERER', 'developer_dashboard'))

# Renders the home page
async def home(request):
    # 1. Resolve Sync Database logic before rendering
    # We check if user is auth and get their username/role safely
    is_auth = await sync_to_async(lambda: request.user.is_authenticated)()
    user_name = await sync_to_async(lambda: request.user.username if is_auth else None)()

    def get_role(user):
        if user.is_superuser:
            return "Admin"
        return user.role

    user_role = await sync_to_async(lambda: get_role(request.user) if is_auth else None)()

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

# Renders the service upload page (must be logged in)
@user_passes_test(developer_check)
def upload_service(request):  # Changed from 'async def' to 'def'
    if request.method == "POST":
        form = AIServiceForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['model_file']

            is_valid, error_msg, hint = True, None, None
            if uploaded_file.name.endswith('.zip'):
                is_valid, error_msg, hint = validate_contract_in_zip(uploaded_file)
            elif uploaded_file.name.endswith('.py'):
                is_valid, error_msg, hint = validate_contract_in_py(uploaded_file)

            if not is_valid:
                form.add_error('model_file', f"Contract Violation: {error_msg}")
                return render(request, "upload_service.html", {
                    "form": form,
                    "error_hint": hint
                })

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

@user_passes_test(developer_check)
def developer_dashboard(request):
    # Only show the logged-in developer's models
    user_models = AIModel.objects.filter(developer=request.user)

    # Optional: split into "models" and "services" for UI clarity
    ai_models = user_models.filter(is_interactive=False)
    ai_services = user_models.filter(is_interactive=True)

    return render(request, "developer_dashboard.html", {
        "ai_models": ai_models,
        "ai_services": ai_services,
    })

@user_passes_test(developer_check)
def delete_ai_model(request, pk):
    model = get_object_or_404(AIModel, pk=pk, developer=request.user)
    model.delete()
    return redirect("developer_dashboard")

@user_passes_test(developer_check)
def edit_ai_model(request, pk):
    model = get_object_or_404(AIModel, pk=pk, developer=request.user)

    # Choose the correct form class
    FormClass = AIServiceForm if model.is_interactive else AIModelForm

    if request.method == "POST":
        form = FormClass(request.POST, request.FILES, instance=model)
        if form.is_valid():
            form.save()
            return redirect("developer_dashboard")
    else:
        form = FormClass(instance=model)

    return render(request, "edit_model.html", {
        "form": form,
        "model": model
    })

@user_passes_test(developer_check)
def model_usage_stats(request, model_id):
    # Ensure the developer only sees stats for their own model
    model = get_object_or_404(AIModel, id=model_id, developer=request.user)
    usages = model.usages.all().order_by('-timestamp')
    return render(request, "model_usage_stats.html", {
        "model": model,
        "usages": usages
    })