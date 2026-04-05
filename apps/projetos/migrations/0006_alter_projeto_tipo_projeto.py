from django.db import migrations, models
import django.contrib.postgres.fields

class Migration(migrations.Migration):
    dependencies = [
        ('projetos', '0005_projeto_desc_obra_projeto_tipo_projeto'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE projetos_projeto
                    ALTER COLUMN tipo_projeto
                    TYPE character varying(50)[]
                    USING (
                        CASE
                            WHEN tipo_projeto IS NULL OR tipo_projeto = '' OR tipo_projeto = 'null'
                                THEN ARRAY[]::character varying(50)[]
                            ELSE ARRAY[tipo_projeto]::character varying(50)[]
                        END
                    );
                    """,
                    reverse_sql="""
                    ALTER TABLE projetos_projeto
                    ALTER COLUMN tipo_projeto
                    TYPE character varying(50)
                    USING (
                        CASE
                            WHEN tipo_projeto IS NULL OR array_length(tipo_projeto, 1) IS NULL
                                THEN 'null'
                            ELSE tipo_projeto[1]
                        END
                    );
                    """,
                )
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='projeto',
                    name='tipo_projeto',
                    field=django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(
                            choices=[
                                ('eletrica', 'Elétrica'),
                                ('hidraulica', 'Hidráulica'),
                                ('alvenaria', 'Alvenaria'),
                                ('spda', 'SPDA'),
                                ('combate_a_incendio', 'Combate a Incêndio'),
                            ],
                            max_length=50,
                        ),
                        default=list,
                    ),
                ),
            ],
        ),
    ]