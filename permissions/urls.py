
from django.urls import path
from core.filters import permitedCompanies
urlpatterns = [
    path('premitted/', ProjectList.as_view(), name='project-list'),    
   
]