from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_aimodel_is_published'),
    ]

    operations = [
        migrations.AddField(
            model_name='modelusage',
            name='output_file',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]