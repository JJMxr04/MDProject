from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_user', '0013_user_aggrigator_api_key_user_aggrigator_external_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
    ]
