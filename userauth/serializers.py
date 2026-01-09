from rest_framework import serializers
from django.contrib.auth.models import User


# class UserListSerializer(serializers.Serializer):

#     username = serializers.CharField(max_length=100)
#     first_name = serializers.CharField(max_length=60)
#     last_name = serializers.CharField(max_length=60)
#     date_joined = serializers.DateTimeField()
    
class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "password" ]
        extra_kwargs = {'password': {'write_only': True}}        

    def create(self, validated_data):
        user = User.objects.create(username=validated_data['username'],
                                       first_name=validated_data['first_name'],
                                       last_name=validated_data['last_name'],
                                         )
        user.set_password(validated_data['password'])
        user.save()
        return user