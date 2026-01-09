# from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import authentication, permissions
from django.contrib.auth.models import User
from permissions.filters import permitedCompanies, IsAllowedFilterBackend
from datetime import datetime
from rest_framework import generics
from rest_framework import status
# class PermittedCompanies(APIView):
#     """
#     * Requires token authentication.
#     * Only admin users are able to access this view.
#     """
#     authentication_classes = [authentication.TokenAuthentication]
#     permission_classes = [permissions.IsAuthenticated]

#     def get(self, request, format=None):
#         """
#         Return a list of all users.
#         """
#         usernames = [user.username for user in User.objects.all()]
#         return Response(usernames)
class AdminListCreateAPIView(generics.ListCreateAPIView):
    # filter_backends = [IsAllowedFilterBackend]
    def post(self, request, *args, **kwargs):
        # request.data._mutable = True

        request.data['created_by'] = request.user.id
        request.data['created_at'] = datetime.now()
        request.data['modified_at'] = request.data['modified_by'] = None
        # request.data._mutable = False
        return self.create(request, *args, **kwargs) 

class AdminRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    # filter_backends = [IsAllowedFilterBackend]
    def put(self, request, *args, **kwargs):

        if 'created_by' in request.data: 
            request.data.pop('created_by')
        if 'created_at' in request.data: 
            request.data.pop('created_at')
        request.data['modified_by'] = request.user.id
        request.data['modified_at'] = datetime.now()
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        # request.data._mutable = True

        if 'created_by' in request.data: 
            request.data.pop('created_by')
        if 'created_at' in request.data: 
            request.data.pop('created_at')
        
        request.data['modified_by'] = request.user.id
        request.data['modified_at'] = datetime.now()
        # request.data._mutable = False
        return self.partial_update(request, *args, **kwargs)    
class GenericsListCreateAPIView(generics.ListCreateAPIView):
    filter_backends = [IsAllowedFilterBackend]

    def post(self, request, *args, **kwargs):
        data = request.data.copy()  # make a mutable copy (works for QueryDict or dict)

        data['created_by'] = data['user'] = request.user.id
        data['created_at'] = datetime.now()
        data['modified_at'] = data['modified_by'] = None

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
# class GenericsListCreateAPIView(generics.ListCreateAPIView):
#     filter_backends = [IsAllowedFilterBackend]
#     def post(self, request, *args, **kwargs):
#         # request.data._mutable = True

#         request.data['created_by'] = request.data['user'] = request.user.id
#         request.data['created_at'] = datetime.now()
#         request.data['modified_at'] = request.data['modified_by'] = None
#         # request.data._mutable = False
#         return self.create(request, *args, **kwargs)    

class GenericsRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    filter_backends = [IsAllowedFilterBackend]
    def put(self, request, *args, **kwargs):
        instance = self.get_object()  # Get the existing instance
        data = request.data.copy()  # Make mutable copy
        
        # Remove protected fields
        data.pop('created_by', None)
        data.pop('created_at', None)
        
        # Add modification info
        data['modified_by'] = request.user.id
        data['modified_at'] = datetime.now()

        # Pass both instance AND data to serializer
        serializer = self.get_serializer(instance, data=data, partial=False)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Typically use HTTP_200_OK for successful updates
        return Response(serializer.data, status=status.HTTP_200_OK)

        # if 'created_by' in request.data: 
        #     request.data.pop('created_by')
        # if 'created_at' in request.data: 
        #     request.data.pop('created_at')
        # request.data['modified_by'] = request.user.id
        # request.data['modified_at'] = datetime.now()
        # return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        
        # if '_mutable' in request.data:
        request.data._mutable = True

        if 'created_by' in request.data: 
            request.data.pop('created_by')
        if 'created_at' in request.data: 
            request.data.pop('created_at')
        
        request.data['modified_by'] = request.user.id
        request.data['modified_at'] = datetime.now()

        # if '_mutable' in request.data:
        request.data._mutable = False

        return self.partial_update(request, *args, **kwargs)    