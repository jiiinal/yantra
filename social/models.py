from django.db import models
from django.contrib.auth.models import User
# Create your models here.
class UserSocialProfile(models.Model):
    user        = models.ForeignKey(User,on_delete=models.DO_NOTHING, related_name = '%(app_label)s_%(class)s_social')    
    telegramId  = models.BigIntegerField()
    email       = models.EmailField(max_length = 254,blank=True, null=True)
    def __str__(self):
        return self.user.username
    
