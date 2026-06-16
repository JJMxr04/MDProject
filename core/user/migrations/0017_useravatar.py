import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_user', '0016_user_potd_streaks'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserAvatar',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='avatar_row', serialize=False, to='core_user.user')),
                ('image', models.BinaryField(blank=True, editable=False, null=True)),
                ('content_type', models.CharField(blank=True, max_length=64, null=True)),
                ('byte_size', models.PositiveIntegerField(default=0)),
                ('etag', models.CharField(blank=True, max_length=64, null=True)),
                ('status', models.CharField(max_length=16)),
                ('source', models.CharField(default='upload', max_length=32)),
                ('fetched', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'core_user_avatar'},
        ),
    ]
