from trading.models import BrokerAccounts
from functools import lru_cache
from utils.cachesettings import get_ttl_hash, CACHE_SETTINGS
@lru_cache(maxsize=24)
def getBrokerAccount(accountId, TTLHash = get_ttl_hash(CACHE_SETTINGS.REFRESH_CACHE_DAILY)):
    return BrokerAccounts.objects.get(id=accountId)