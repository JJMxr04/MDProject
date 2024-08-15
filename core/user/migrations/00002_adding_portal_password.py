from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_user', '0001_initial'),  # Ensure this matches the name of your app and the first migration file
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='portal_password',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
    ]
