import core.event.models.team
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core_event', '0001_initial'),  # Depend on the first migration
    ]

    operations = [
        migrations.CreateModel(
            name='Bookmaker',
            fields=[
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('key', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('last_update', models.DateTimeField()),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookmakers', to='core_event.event')),
            ],
            options={
                'db_table': 'core.bookmaker',
            },
        ),
        migrations.CreateModel(
            name='Market',
            fields=[
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('key', models.CharField(max_length=255)),
                ('last_update', models.DateTimeField()),
                ('bookmaker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='markets', to='core_event.bookmaker')),
            ],
            options={
                'db_table': 'core.market',
            },
        ),
        migrations.CreateModel(
            name='Outcome',
            fields=[
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=50)),
                ('price', models.FloatField()),
                ('point', models.FloatField(null=True)),
                ('market', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outcomes', to='core_event.market')),
            ],
            options={
                'db_table': 'core.outcome',
            },
        ),
    ]
