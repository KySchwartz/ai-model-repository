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

class AIServiceForm(forms.ModelForm):
    class Meta:
        model = AIModel
        fields = ['title', 'model_file', 'framework', 'version', 'input_type', 'output_type', 'output_extension']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Force these to be required for this specific form
        self.fields['input_type'].required = True
        self.fields['output_type'].required = True