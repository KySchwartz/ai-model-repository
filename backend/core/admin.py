from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, AIModel

# Register the Custom User model
admin.site.register(User, UserAdmin)

# Register the AIModel model
@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    # This controls which columns show up in the list view
    list_display = ('title', 'description', 'developer', 'framework', 'version', 'upload_date')
    # This adds a search bar for specific fields
    search_fields = ('title', 'framework')
    # This adds a filter sidebar
    list_filter = ('framework', 'upload_date')