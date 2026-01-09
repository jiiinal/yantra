from functools import lru_cache
# from mainapp.models import UserSocialProfile
from social.models import UserSocialProfile
from time import time as tm
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.conf import settings

CACHE_TTL = getattr(settings, 'CACHE_TTL', DEFAULT_TIMEOUT)

class CACHE_SETTINGS:
    REFRESH_CACHE_WEEKLY = 60 * 60 * 24 * 7 #Daily Seconds * minutes * hours
    REFRESH_CACHE_DAILY = 60 * 60 * 24      #Daily Seconds * minutes * hours
    REFRESH_CACHE_HOURLY = 60 * 60          #Hourly Seconds * minutes
    REFRESH_CACHE_12HOUR = 60 * 60 * 12     #Hourly Seconds * minutes
    REFRESH_CACHE_5MINUTES = 60 * 5         #Hourly Seconds * minutes
    REFRESH_CACHE_10MINUTES = 60 * 10       #Hourly Seconds * minutes
    REFRESH_CACHE_30MINUTES = 60 * 30       #Hourly Seconds * minutes

def get_ttl_hash(seconds= CACHE_SETTINGS.REFRESH_CACHE_DAILY):
    if seconds == 0:
        seconds = CACHE_TTL
    """Return the same value withing `seconds` time period"""
    return round(tm() / seconds)