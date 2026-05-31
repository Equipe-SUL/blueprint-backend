from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import PerfilMilitar


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'email', 'username']

class RegistroSerializer(serializers.ModelSerializer):
    telefone = serializers.CharField(write_only=True, required=False)
    matricula = serializers.CharField(write_only=True)
    patente = serializers.CharField(write_only=True)
    unidade = serializers.CharField(write_only=True)
    senha = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('first_name', 'email', 'senha', 'telefone', 'matricula', 'patente', 'unidade')

    def validate_senha(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este email já está cadastrado.")
        return value

    def validate_matricula(self, value):
        if PerfilMilitar.objects.filter(matricula=value).exists():
            raise serializers.ValidationError("Esta matrícula já está cadastrada.")
        return value

    def create(self, validated_data):
        email = validated_data['email']
        senha = validated_data['senha']
        first_name = validated_data.get('first_name', '')

        user = User.objects.create_user(
            username=email, 
            email=email,
            password=senha,
            first_name=first_name
        )

        PerfilMilitar.objects.create(
            user=user,
            telefone=validated_data.get('telefone', ''),
            matricula=validated_data.get('matricula'),
            patente=validated_data.get('patente'),
            unidade=validated_data.get('unidade')
        )

        return user