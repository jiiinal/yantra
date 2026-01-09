from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from django.core.exceptions import ValidationError
# Create your models here.
class organization(models.Model):
    name = models.CharField(max_length=80,null=False,blank=False)

    def __str__(self):
            return self.name
    
class company(models.Model):
    name = models.CharField(max_length=80,null=False,blank=False)
    organization = models.ForeignKey(organization,on_delete=models.CASCADE, blank=False,null=False,related_name='company_organization')
    def __str__(self):
            return f'{self.name} ({self.organization})'
    
class userprofile(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE, related_name='user_profile')
    company = models.ForeignKey(company,on_delete=models.CASCADE,null=True,blank=True,related_name='user_company')
    organization = models.ForeignKey(organization,on_delete=models.CASCADE,null=True,blank=True,related_name='user_organization')
    def __str__(self):
        if self.organization:
            return f'{self.user}-{self.organization}'
        else:
            return f'{self.user}-{self.company}'
        
class UserAudit(models.Model):
    company = models.ForeignKey(company,on_delete=models.CASCADE,null=True,blank=True,related_name='%(class)s_audit_company')
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,null=True, blank=True, on_delete=models.CASCADE, related_name='%(class)s_createdby')
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='%(class)s_modifiedby', null=True, blank=True)
    class Meta:
        abstract = True

    # def clean(self):
    #     if not len(self.company) > 10:
    #         raise ValidationError(
    #             {'title': "Title should have at least 10 letters"})

    def save(self, *args, **kwargs):
        # if self.company.id > 0:
        #     raise ValidationError(
        #         {'title': "Title should have at least 10 letters"})    
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

