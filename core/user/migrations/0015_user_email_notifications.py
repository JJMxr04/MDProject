from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_user', '0014_user_date_of_birth'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_notifications',
            field=models.BooleanField(default=True),
        ),
    ]
