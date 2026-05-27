import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PerfilMilitar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telefone', models.CharField(blank=True, max_length=20, null=True)),
                ('matricula', models.CharField(max_length=50, unique=True)),
                ('patente', models.CharField(choices=[('Soldado', 'Soldado'), ('Cabo', 'Cabo'), ('Terceiro-Sargento', 'Terceiro-Sargento'), ('Segundo-Sargento', 'Segundo-Sargento'), ('Primeiro-Sargento', 'Primeiro-Sargento'), ('Subtenente', 'Subtenente'), ('Segundo-Tenente', 'Segundo-Tenente'), ('Primeiro-Tenente', 'Primeiro-Tenente'), ('Capitão', 'Capitão'), ('Major', 'Major'), ('Tenente-Coronel', 'Tenente-Coronel'), ('Coronel', 'Coronel'), ('General-de-Brigada', 'General-de-Brigada'), ('General-de-Divisão', 'General-de-Divisão'), ('General-de-Exército', 'General-de-Exército')], max_length=50)),
                ('unidade', models.CharField(choices=[('6° Batalhão de Infantaria Leve do Exército', '6° Batalhão de Infantaria Leve do Exército'), ('Comando da 12 Brigada de Infantaria Leve Aeromovel', 'Comando da 12 Brigada de Infantaria Leve Aeromovel')], max_length=150)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='perfil', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]