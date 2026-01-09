from django.db import models
from django.conf import settings
from django.utils import timezone
# Create your models here.
class UserAudit(models.Model):
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