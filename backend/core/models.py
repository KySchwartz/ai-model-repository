from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    # Define the roles as specific choices 
    ROLE_CHOICES = (
        ('consumer', 'Consumer'),
        ('developer', 'Developer'),
        ('admin', 'Administrator'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='consumer')
    
    # REQ-PAY-1: Maintain a Credit Balance for each user 
    credit_balance = models.IntegerField(default=10)