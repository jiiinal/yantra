from django.contrib import admin
from trading.models import Brokers, BrokerAccounts, MarketSessions, Strategis, JobbingSettings, Exchanges, Scripts
from trading.models import JobbingLog
# Register your models here.

admin.site.register(Brokers)
admin.site.register(Exchanges)
admin.site.register(BrokerAccounts)

admin.site.register(MarketSessions)
admin.site.register(Strategis)
admin.site.register(JobbingSettings)
admin.site.register(JobbingLog)
admin.site.register(Scripts)
