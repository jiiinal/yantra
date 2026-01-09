from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import permissions

from django.shortcuts import render
from rest_framework.views import APIView
from userauth.serializers import UserSerializer
from rest_framework import generics

from rest_framework.response import Response

def get_user(userid=None):
    users = User.objects.all()
    if userid:
        users = users.filter(id = userid)
    return users


# view for registering users
class RegisterView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        serializer.fields.pop('password')
        return Response(serializer.data)
    
class UserListView(generics.ListCreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        # Note the use of `get_queryset()` instead of `self.queryset`
        queryset = self.get_queryset()
        serializer = UserSerializer(queryset, many=True)
        return Response(serializer.data)
        
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        serializer.fields.pop('password')
        return Response(serializer.data)        
    
class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'username'
    permission_classes = [permissions.IsAuthenticated]

