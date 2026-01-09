from trading.views.Entities.brokerAccount import BrokerAccount
from trading.models import Scripts, Strategy1Log
from django.db.models import Q
from trading.views.Strategies.strategy import Strategy
from datetime import datetime
import pytz

class OrdersAndTrade():
    def __init__(self, brokerAccount: BrokerAccount, accountId = None)->None:
        self.brokerAccount = brokerAccount
        self.accountId = accountId


    def getOrderLog(self, strategyCode, exchSeg, token, startDate, endDate, accountId=0, symbol=None, status = 'COMPLETE' ):
        if accountId == 0:
            accountId = self.accountId
        qFilter = Q(exchSeg = exchSeg)
        if token == 0 and symbol != '':
            qFilter &= Q(symbol = symbol)
        if token > 0 :
            qFilter &= Q(token = token)
        
        # script = Scripts.objects.filter(qFilter).first()
        strategy = Strategy.getStrategyInstance(self.brokerAccount.User, strategyCode, exchSeg)        
        if strategy:
            return strategy.getOrderLog(startDate = startDate, endDate = endDate, exchange = exchSeg, token = token, symbol = symbol, brokerAccountId = accountId, status = status)
            # self.brokerAccount.getHistoricalData(accountId,exchSeg,script.symbol,script.token,fromdate,todate, interval)
        else:
            return None
    
    def getColumnDefs(self):
        fields = ['target__nickName','exchSeg','token','symbol','orderType','orderId','tradeDate','quantity','price','currStock','status','updatedOn' ]
        colDef = [
            {'field':'target__nickName', 'flex': 2 },
            {'field':'exchSeg', 'flex': 1 },
            {'field':'token', 'flex': 1 },
            {'field':'symbol', 'flex': 1 },
            {'field':'orderType', 'flex': 1 },
            {'field':'orderId', 'flex': 2 },
            {'field':'tradeDate', 'flex': 2 },
            {'field':'quantity', 'flex': 1 },
            {'field':'price', 'flex': 1 },
            {'field':'currStock', 'flex': 1 },
            {'field':'status', 'flex': 1 },
            {'field':'updatedOn', 'flex': 2 } 
            ]        
        return fields, colDef

    def getOrderBook(self, exchSeg, token, orderId, symbol=None, accountId=None):
        orderbook = self.brokerAccount.readOrderBook(accountId,orderId)
        return orderbook
