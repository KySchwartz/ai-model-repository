Python

from django.contrib.auth.models import AbstractUser

from django.db import models

from django.shortcuts import render

def home(request):
    return render(request, "home.html")


class User(AbstractUser):

ROLE_CHOICES = (

    ('consumer', 'Consumer'),

    ('developer', 'Developer'),

    ('admin', 'Admin'),

)

role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='consumer')

credit_balance = models.IntegerField(default=10) # SRS Requirement for monetization

class AIModel(models.Model):

    developer = models.ForeignKey(User, on_delete=models.CASCADE)

    title = models.CharField(max_length=200)

    description = models.TextField()

    framework = models.CharField(max_length=50) # e.g., XGBoost, Random Forest

    version = models.CharField(max_length=10, default="1.0.0")

    model_file = models.FileField(upload_to='models/')

    upload_date = models.DateTimeField(auto_now_add=True)