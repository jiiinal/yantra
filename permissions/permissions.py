from rest_framework.permissions import BasePermission

from django.db.models import Q



class IsOwnerPermission(BasePermission):
    """
    Custom permission to only allow owners of an object to edit or delete it.
    """

    def has_object_permission(self, request, view, obj):
        # Check if the user is the owner of the object
        return obj.user == request.user
    
class CompanyPermission(BasePermission):
    def has_permission(self, request, view):
        # compids = permitedCompanies(request.user)                
        return request.user.is_authenticated #and view.queryset.filter(company_id__in = compids).exists()  
        
    def has_object_permission(self, request, view, obj):
        return True
        # Check if the user is the owner of the object
        qFilter = Q(user = request.user)
        if obj.company:
            qFilter &=  Q(company=obj.company) | Q(organization = obj.company.organization)
        else:
            return obj.created_by == request.user or obj.company is None
        return userprofile.objects.filter(qFilter).exists()    