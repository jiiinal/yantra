from django.contrib import admin
from permissions.models.audit import organization, company, userprofile
# Register your models here.

admin.site.register(organization)
admin.site.register(company)
admin.site.register(userprofile)