from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_user', '0018_remove_user_avatar'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='home_color',
            field=models.CharField(blank=True, max_length=9, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='away_color',
            field=models.CharField(blank=True, max_length=9, null=True),
        ),
    ]
