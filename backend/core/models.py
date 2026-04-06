from django.contrib.auth.models import AbstractUser
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_delete
from django.db.models.signals import pre_save

class User(AbstractUser):

    ROLE_CHOICES = (

        ('consumer', 'Consumer'),

        ('developer', 'Developer'),

        ('admin', 'Admin'),

    )

    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='consumer')

    credit_balance = models.IntegerField(default=10)


class AIModel(models.Model):
    # Existing fields
    developer = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    framework = models.CharField(max_length=50)
    version = models.CharField(max_length=10, default="1.0.0")
    model_file = models.FileField(upload_to='models/')
    upload_date = models.DateTimeField(auto_now_add=True)
    
    # Flexible service fields
    is_interactive = models.BooleanField(default=False)
    
    # These choices allow the system to adapt to any AI service
    INPUT_CHOICES = [('text', 'Text Input'), ('file', 'File Upload')]
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
    
    input_type = models.CharField(max_length=50, choices=INPUT_CHOICES, blank=True, null=True)
    output_type = models.CharField(max_length=50, choices=OUTPUT_CHOICES, blank=True, null=True)
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