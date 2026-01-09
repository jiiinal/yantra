from trading.Entities.BrokerAccounts.brokerAccount import BrokerAccount
from trading.models import Scripts
from django.db.models import Q

class HistoricalData():
    def __init__(self, brokerAccount: BrokerAccount, accountId = None)->None:
        self.brokerAccount = brokerAccount
        self.accountId = accountId


    def getHistoricCandleData(self, exchSeg, token, fromdate, todate, accountId=0, interval = 1,symbol=''):
        if accountId == 0:
            accountId = self.accountId
        qFilter = Q(exchSeg = exchSeg)
        if token == 0 and symbol != '':
            qFilter &= Q(symbol = symbol)
        if token > 0 :
            qFilter &= Q(token = token)
        
        script = Scripts.objects.filter(qFilter).first()
        if script:
            return self.brokerAccount.getHistoricalData(accountId,exchSeg,script.symbol,script.token,fromdate,todate, interval)
        else:
            return None
