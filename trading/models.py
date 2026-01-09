from django.db import models
# from userauth.models import UserData
from django.contrib.auth.models import User
from userauth.models import UserAudit
# Create your models here.

# Create your models here.
class Brokers(models.Model):
    brokerId    = models.SmallIntegerField(unique=True, null=False, blank=False)
    brokerName  = models.CharField(max_length=255,unique=True,null=False, blank=False)
    className   = models.CharField(max_length=40,unique=True,null=False, blank=False)
    def __str__(self):
        return self.brokerName

class Exchanges(models.Model):
    code = models.CharField(max_length=3, null=False, blank=False)
    name = models.CharField(max_length=20)
    def __str__(self) -> str:
        return self.name

class MarketSessions(models.Model):
    broker = models.ForeignKey(Brokers,on_delete=models.CASCADE,blank=True, null = True, related_name = '%(app_label)s_%(class)s_MSession_Broker')
    exchange = models.ForeignKey(Exchanges,on_delete=models.CASCADE,blank=True, null = True, related_name = '%(app_label)s_%(class)s_MSession_Exchange')
    startTime = models.TimeField()
    EndTime = models.TimeField()

    def __str__(self):
        return self.exchange.name + "-" + str(self.startTime) + "-"+ str(self.EndTime)
    
class BrokerAccounts(UserAudit):
    user            = models.ForeignKey(User,on_delete=models.DO_NOTHING, blank=True, null=True, related_name = '%(app_label)s_%(class)s_brokeraccs')
    broker          = models.ForeignKey(Brokers,on_delete=models.DO_NOTHING, blank=True, null=True, related_name = '%(app_label)s_%(class)s_broker')
    nickName        = models.CharField(max_length=80)
    apiKey          = models.CharField(max_length=40)
    clientId        = models.CharField(max_length=40)
    password        = models.CharField(max_length=40)
    factor2         = models.CharField(max_length=40,default='', null=True, blank=True)
    factor2Secret   = models.CharField(max_length=128,default='', null=True, blank=True)    
    vendorCode      = models.CharField(max_length=20,default='', null=True, blank=True)
    reqToken        = models.CharField(max_length=128,default='', null=True, blank=True)
    feedToken       = models.CharField(max_length=128,default='', null=True, blank=True)
    acccessToken    = models.CharField(max_length=128,default='', null=True, blank=True)
    apiSecret       = models.CharField(max_length=128,null=True,blank=True, default='')
    isActive        = models.BooleanField(null=False, blank=False, default=False)
    def __str__(self):
        return self.nickName    
    
class Scripts(models.Model):
    token           = models.CharField(max_length=40)
    symbol          = models.CharField(max_length=40)
    symbolFinvasia  = models.CharField(max_length=40,default='') 
    name            = models.CharField(max_length=40) 
    expiry          = models.CharField(max_length=40, null=True, blank=True)
    strike          = models.DecimalField(max_digits=30,decimal_places=10)
    lotSize         = models.IntegerField()
    instrumentType  = models.CharField(max_length=24) 
    exchSeg         = models.CharField(max_length=40) 
    segment         = models.CharField(max_length=40, default='')
    tickSize        = models.DecimalField(max_digits=30,decimal_places=10)
    optionType      = models.CharField(max_length=2, default='')
    GNGD            = models.DecimalField(max_digits=12,decimal_places=5, default=1)
    precision       = models.IntegerField(default=2)
    multiplier      = models.IntegerField(default=2)
    def __str__(self):
        return self.symbol + '-' + self.name + '-' + self.token    

class Strategis(models.Model):
    code        = models.CharField(max_length=20, null=True, blank=True, default = '')
    name        = models.CharField(max_length=80, null=True, blank=True, default=None)
    className   = models.CharField(max_length = 100, null=True, blank=True, default = '')
    isActive    = models.BooleanField(default = False)
    def __str__(self):
        return self.code + '-' + self.name
    
class StrategyStatus(models.Model):
    user            = models.ForeignKey(User,on_delete=models.DO_NOTHING, blank=True, null=True, related_name = '%(app_label)s_%(class)s_statususer')        
    strategy        = models.ForeignKey(Strategis, on_delete=models.CASCADE, blank=False, null=False,related_name = '%(app_label)s_%(class)s_statusstrategy') 
    currStatus      = models.CharField(max_length=10)
    forceStop       = models.BooleanField(default = False)
    taskId          = models.CharField(max_length = 40, default = None, null=True, blank=True)
    def __str__(self):
        return str(self.strategy.name)
    
    
class JobbingSettings(UserAudit):
    user            = models.ForeignKey(User,on_delete=models.DO_NOTHING, blank=True, null=True, related_name = '%(app_label)s_%(class)s_cycleOrder')        
    exchange        = models.ForeignKey(Exchanges,on_delete=models.CASCADE,blank=True, null = True, related_name = '%(app_label)s_%(class)s_Jobbing_Exchange')
    token           = models.CharField(max_length=40)
    stockInitial    = models.IntegerField()
    buyLot          = models.IntegerField()
    buyTick         = models.DecimalField(max_digits=7,decimal_places=2)
    sellLot         = models.IntegerField(default=0)    
    sellTick        = models.DecimalField(max_digits=7,decimal_places=2, default = 0 )
    priceBase       = models.DecimalField(max_digits=10,decimal_places=2)
    priceCurrent    = models.DecimalField(max_digits=10,decimal_places=2, default=0)   #Price to start the trade even the previous logs exists
    stockCurrent    = models.IntegerField(default=0)
    stockMax        = models.IntegerField(default=0)
    stockMin        = models.IntegerField(default=0)
    target          = models.ForeignKey(BrokerAccounts,on_delete=models.DO_NOTHING, blank=False, null=False)    
    dayOrders       = models.IntegerField(default = 3)
    isActive        = models.BooleanField(null=False, blank=False, default=False)    
    simulate        = models.BooleanField(null=False, blank=False, default=True)    
    symbol          = models.CharField(max_length=40, null=True, blank=True) 
    orderCatagory   = models.CharField(max_length=12, null=True, blank=True, default='Normal') 
    gttBuyBuffer    = models.DecimalField(max_digits=7,decimal_places=2, default=0)
    gttSellBuffer   = models.DecimalField(max_digits=7,decimal_places=2, default=0)
    wait            = models.IntegerField(default = 0) #Wait in seconds for checking if order can be place
    count           = models.IntegerField(default = 1) #related to wait value, wait for {count} time to check if ord can be place

    def __str__(self):
        return self.user.username + ':' + self.symbol + '{' + str(self.buyTick) + '/' + str(self.buyLot) + ')'


class JobbingLog(models.Model):
    user            = models.ForeignKey(User,on_delete=models.DO_NOTHING, blank=True, null=True, related_name = '%(app_label)s_%(class)s_cycleLog')        
    target          = models.ForeignKey(BrokerAccounts,on_delete=models.DO_NOTHING, blank=False, null=False, related_name = '%(app_label)s_%(class)s_cycleTarget')    
    exchange        = models.ForeignKey(Exchanges,on_delete=models.CASCADE,blank=True, null = True, related_name = '%(app_label)s_%(class)s_Jobbing_Exchange')
    token           = models.CharField(max_length=40)
    symbol          = models.CharField(max_length=40, null=True, blank=True) 
    orderId         = models.CharField(max_length=20) 
    tradeDate       = models.DateTimeField()
    quantity        = models.IntegerField()
    price           = models.DecimalField(max_digits=10,decimal_places=2)
    orderType       = models.CharField(max_length=4)
    intraday        = models.BooleanField(default=False)
    currStock       = models.IntegerField()
    status          = models.CharField(max_length=40)
    updatedOn       = models.DateTimeField(auto_now=False, null=True, blank=True)
    orderCategory   = models.CharField(max_length=12, null=True, blank=True, default='Normal')
    def __str__(self):
        return self.token + '-' + str(self.tradeDate) + '-' + str(self.target_id)