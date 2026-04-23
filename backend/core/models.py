from django.contrib.auth.models import AbstractUser
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_delete
from django.db.models.signals import pre_save
from django.utils import timezone

class User(AbstractUser):

    ROLE_CHOICES = (
        ('consumer', 'Consumer'),
        ('developer', 'Developer'),
        ('admin', 'Admin'),
    )

    # User information fields
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='consumer')
    credit_balance = models.IntegerField(default=5)
    purchased_credits = models.IntegerField(default=0)
    is_subscribed = models.BooleanField(default=False)
    last_credit_refresh = models.DateTimeField(default=timezone.now)
    subscription_expiry = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Automatically grant Django Admin/Staff status if role is set to 'admin'
        if self.role == 'admin':
            self.is_staff = True
            self.is_superuser = True
        super().save(*args, **kwargs)

class AIModel(models.Model):
    # Existing fields
    developer = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    framework = models.CharField(max_length=50)
    version = models.CharField(max_length=10, default="1.0.0")
    model_file = models.FileField(upload_to='models/')
    image = models.ImageField(upload_to='service_images/', blank=True, null=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    
    # Flexible service fields
    is_interactive = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    
    # These choices allow the system to adapt to any AI service
    INPUT_CHOICES = [
        ('text', 'Text Input'), 
        ('file', 'File Upload'),
        ('custom', 'Custom UI (JSON Config)'),
    ]
    OUTPUT_CHOICES = [('text', 'Text Result'), ('file', 'File/Image Download')]
    EXT_CHOICES = [
        ('', 'Custom/Detect from Code'),
        ('.docx', 'Word Document (.docx)'),
        ('.csv', 'CSV Spreadsheet (.csv)'), 
        ('.txt', 'Text File (.txt)'),
        ('.pdf', 'PDF Document (.pdf)'),
        ('.png', 'Image File (.png)'),
        ('.xlsx', 'Excel Spreadsheet (.xlsx)'),
        ('.zip', 'Zip Archive (.zip)'),
        ('.json', 'JSON File (.json)'),
    ]
    
    # Service fields
    input_type = models.CharField(max_length=50, choices=INPUT_CHOICES, blank=True, null=True)
    output_type = models.CharField(max_length=50, choices=OUTPUT_CHOICES, blank=True, null=True)
    ui_config_file = models.FileField(upload_to='ui_configs/', blank=True, null=True)
    output_extension = models.CharField(max_length=10, choices=EXT_CHOICES, default='', blank=True, null=True)

    def __str__(self):
        return self.title
 
@receiver(post_delete, sender=AIModel)
def delete_model_file(sender, instance, **kwargs):
    if instance.model_file:
        instance.model_file.delete(save=False)

@receiver(pre_save, sender=AIModel)
def replace_model_file(sender, instance, **kwargs):
    if not instance.pk:
        return  # new model, nothing to replace

    try:
        old_file = AIModel.objects.get(pk=instance.pk).model_file
    except AIModel.DoesNotExist:
        return

    new_file = instance.model_file
    if old_file and old_file != new_file:
        old_file.delete(save=False)

class ModelUsage(models.Model):
    # Fields to track usage statistics of AI services
    model = models.ForeignKey(AIModel, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    init_time_seconds = models.FloatField(default=0)
    execution_time_seconds = models.FloatField(default=0)
    peak_memory_mb = models.FloatField(null=True, blank=True)
    cpu_usage_seconds = models.FloatField(null=True, blank=True)
    input_size_bytes = models.IntegerField(default=0)
    output_token_count = models.IntegerField(null=True, blank=True)
    output_type = models.CharField(max_length=50, blank=True)
    error_code = models.CharField(max_length=50, default='SUCCESS')
    status = models.CharField(max_length=20) # 'success' or 'error'

    def __str__(self):
        user_label = self.user.username if self.user else "Anonymous"
        return f"{self.model.title} used by {user_label} at {self.timestamp}"