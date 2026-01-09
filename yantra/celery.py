from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
# celery -A yantra worker --loglevel=info --pool=gevent --concurrency=10
# celery -A yantra flower


os.environ.setdefault('DJANGO_SETTINGS_MODULE','yantra.settings')

app = Celery('yantra')

app.conf.enable_utc = False

app.conf.update(timezone = 'Asia/Kolkata')

app.config_from_object(settings, namespace='CELERY')

#Celery Beats
app.conf.beat_schedule = {
    
}
app.loader.override_backends['django-db'] = 'django_celery_results.backends.database:DatabaseBackend'
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')