from django import forms 
from .models import AIModel 
from django.contrib.auth.forms import UserCreationForm
from .models import User
 
class AIModelForm(forms.ModelForm): 
   class Meta: 
       model = AIModel 
       fields = ["title", "description", "framework", "version", "model_file"] 
 
class CustomSignupForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        # This adds the 'role' field from your model to the registration form
        fields = UserCreationForm.Meta.fields + ('role',)