"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views 
from django.conf import settings 
from django.conf.urls.static import static
from django.contrib import admin

urlpatterns = [
    # Home Path 
    path("", views.home, name="home"),
   
    # Models Path 
    path("models/", views.model_list, name="model_list"),
    path("services/", views.ai_service_catalog, name="service_catalog"),
    path("services/run/<int:model_id>/", views.model_service_page, name="model_service_page"),

    # Upload Path
    path("upload/", views.upload_model, name="upload_model"), 

    # Upload Path for AI Services
    path("upload-service/", views.upload_service, name="upload_service"),

    # Authentication Paths
    path("signup/", views.signup_view, name="signup"),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'), 
    path('logout/', auth_views.LogoutView.as_view(), name='logout'), 
    path("account/", views.account_management, name="account_management"),
    path("account/checkout/", views.checkout_view, name="checkout"),
    path("account/process-payment/", views.process_payment, name="process_payment"),

    # Developer Paths
    path("developer/dashboard/", views.developer_dashboard, name="developer_dashboard"),
    path("developer/models/<int:pk>/edit/", views.edit_ai_model, name="edit_ai_model"),
    path("developer/models/<int:pk>/delete/", views.delete_ai_model, name="delete_ai_model"),
    path("developer/models/<int:model_id>/usage/", views.model_usage_stats, name="model_usage_stats"),
    path("developer/models/<int:model_id>/publish/", views.toggle_publish_status, name="toggle_publish_status"),

    #Admin Path
    path('admin/', admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
