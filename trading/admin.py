from django.contrib import admin
from trading.models import Brokers, BrokerAccounts, MarketSessions, Strategis, JobbingSettings, Exchanges, SwingLog, SwingSettings, Scripts
from trading.models import JobbingLog

# Register your models here.

admin.site.register(Brokers)
admin.site.register(Exchanges)


class BrokerAccountsAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'nickName', 'isActive')
    list_filter = ('user', 'isActive')


class JobbingSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'isActive', 'exchange', 'buyLot', 'buyTick', 'sellLot', 'sellTick', 'priceBase', 'priceCurrent', 'token')


class JobbingLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'orderId', 'orderType', 'target', 'exchange', 'quantity', 'price', 'currStock', 'status', 'updatedOn')


class SwingSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'user__username', 'exchange', 'isActive', 'lot', 'slLot', 'gap', 'stopLoss', 'token', 'stockCurrent', 'priceCurrent', 'useSlLot', 'symbol')
    list_filter = ('isActive',)


class SwingLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'orderId', 'orderType', 'target', 'exchange', 'quantity', 'price', 'currStock', 'status', 'updatedOn')


class ScriptsAdmin(admin.ModelAdmin):
    list_display = ('id', 'exchSeg', 'token', 'symbol', 'name', 'expiry', 'expiryDate', 'lotSize')
    list_filter = ('exchSeg',)


admin.site.register(BrokerAccounts, BrokerAccountsAdmin)

admin.site.register(MarketSessions)
admin.site.register(Strategis)
admin.site.register(JobbingSettings, JobbingSettingsAdmin)
admin.site.register(JobbingLog, JobbingLogAdmin)
admin.site.register(Scripts, ScriptsAdmin)
admin.site.register(SwingSettings, SwingSettingsAdmin)
admin.site.register(SwingLog, SwingLogAdmin)
