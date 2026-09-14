from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0032_publicwebform_publicformsession'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppInstallCode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255)),
                ('code', models.CharField(max_length=16, unique=True)),
                ('target_url', models.TextField()),
                ('created_on', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'unique_together': {('domain', 'target_url')},
            },
        ),
    ]
