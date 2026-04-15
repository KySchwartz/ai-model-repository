import os
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.management import call_command
from .models import User, AIModel, ModelUsage

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

    # Add additional actions for AI models
    actions = ["clean_orphaned_model_files", "run_cleanup_outputs"]

    def clean_orphaned_model_files(self, request, queryset=None):
        """
        Admin action: Remove files in /media/models/ that are not referenced by any AIModel.
        """
        models_dir = os.path.join(settings.MEDIA_ROOT, "models")
        os.makedirs(models_dir, exist_ok=True)

        # Files physically on disk
        disk_files = set(os.listdir(models_dir))

        # Files referenced in DB
        db_files = set(
            os.path.basename(model.model_file.name)
            for model in AIModel.objects.all()
            if model.model_file
        )

        # Orphaned files
        orphaned = disk_files - db_files

        if not orphaned:
            messages.info(request, "No orphaned files found.")
            return

        deleted_count = 0
        for filename in orphaned:
            try:
                os.remove(os.path.join(models_dir, filename))
                deleted_count += 1
            except Exception as e:
                messages.error(request, f"Error deleting {filename}: {e}")

        messages.success(request, f"Deleted {deleted_count} orphaned model file(s).")

    clean_orphaned_model_files.short_description = "Clean orphaned model files"

    def run_cleanup_outputs(self, request, queryset=None):
        """
        Admin action: Trigger the management command to purge old temporary outputs.
        """
        try:
            call_command('cleanup_outputs')
            messages.success(request, "Cleanup of temporary output files completed successfully.")
        except Exception as e:
            messages.error(request, f"Error running cleanup command: {e}")

    run_cleanup_outputs.short_description = "Purge temporary outputs (>24h old)"

@admin.register(ModelUsage)
class ModelUsageAdmin(admin.ModelAdmin):
    list_display = ('model', 'user', 'timestamp', 'execution_time_seconds', 'peak_memory_mb', 'cpu_usage_seconds', 'status')
    list_filter = ('status', 'timestamp', 'model')
    search_fields = ('model__title', 'user__username')
