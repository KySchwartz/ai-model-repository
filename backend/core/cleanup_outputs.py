import os
import time
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Cleans up temporary files in temp_uploads older than 24 hours'

    def handle(self, *args, **options):
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
        
        if not os.path.exists(temp_dir):
            self.stdout.write(self.style.WARNING(f"Directory {temp_dir} does not exist. Skipping cleanup."))
            return

        now = time.time()
        retention_seconds = 24 * 60 * 60  # 24 hours
        deleted_count = 0

        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                if os.stat(file_path).st_mtime < (now - retention_seconds):
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except Exception as e:
                        self.stderr.write(f"Failed to delete {filename}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted_count} orphaned temporary files."))