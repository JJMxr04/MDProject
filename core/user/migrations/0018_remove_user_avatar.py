from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core_user', '0017_useravatar'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='avatar',
        ),
    ]
