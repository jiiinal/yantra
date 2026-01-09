import pandas as pd

from trading.Entities.Brokers.broker import Broker
from django.db.models import Q
import numbers, datetime, decimal
from django.http import HttpResponse
from numpy import isnan
from celery import shared_task
from trading.Strategies.strategyManager import StrategyManager
from django.contrib.auth.models import User
from trading.models import BrokerAccounts, Strategis, Scripts
from trading.Strategies.strategy import Strategy
from trading.Entities.Exchanges.india import Exchange
from social.views.telegram import Telegram
from trading.Redis.pubsub import PubSub
from django.contrib.auth.models import User
       
FINVASIA_SYMBOLS_NSE_PATH = {
    'NSE': 'https://api.shoonya.com/NSE_symbols.txt.zip',
    'BSE': 'https://api.shoonya.com/BSE_symbols.txt.zip',
    'NFO': 'https://api.shoonya.com/NFO_symbols.txt.zip',
    'CDS': 'https://api.shoonya.com/CDS_symbols.txt.zip',
    'MCX': 'https://api.shoonya.com/MCX_symbols.txt.zip',
    }

@shared_task(bind=True)
def startStrategyManagerForAll(self):
    try:
        users = User.objects.all()
        for user in users:
            print(user.username)
            startStrategyManager.delay(user.id)            
    except Exception as e:
        print(str(e))



@shared_task(bind=True)
def startStrategyManager(self, userid, exchange=None):
    try:

        user = User.objects.filter(id = userid).first()           
        telegram = Telegram(userid)
        telegram.sendMessage(f'Strategy Manager initiated for User {user.username}')

        manager = StrategyManager(user)
        manager.initiate(exchange)
        manager.start(exchange)
        
        telegram.sendMessage(f'Strategy Manager Started for User {user.username}')
    except Exception as e:
        pass

@shared_task(bind=True)
def stopStrategyManager(self, userid, exchange=None):
    try:
        user = User.objects.filter(id = userid).first() 
        broker = Broker(0)
        brokerAccs = BrokerAccounts.objects.filter(user = user)
        exchange = Exchange(exchange)
        strategies = Strategis.objects.all()
        telegram = Telegram(userid)
        for strat in strategies:
            strategy = Strategy.getStrategyInstance(user, strat.code, exchange)
            if strategy:
                if strategy.isActive:
                    for accs in brokerAccs:
                        for exch in exchange.getExchanges():
                            if strategy.requireOrderCallback:
                                QueueID = broker.getQueueId(user.username,accs.clientId,exch.code,'O')
                                pubsub = PubSub(QueueID)
                                message = {'type': 'TERMINATE', 'exchange': exch.code, 'strategy': strategy.code}
                                pubsub.publish(QueueID,message)

                                telegram.sendMessage(f'Strategy Termination initiated for User {user.username}')
    except Exception as e:
        telegram.sendMessage(f'Error : Strategy Termination init for User {user.username}')


def syncSymbolsReq(request):
    syncSymbols()
    HttpResponse('symbol sync completed')
    
@shared_task(bind = True)
def syncSymbols(self):
    manager = MasterDataManager(3)
    manager.syncSymbols()

class MasterDataManager():
    def __init__(self, brokerId):
        self.BrokerId = brokerId

    def getSymbolField(self,brokerId=0):
        fieldName = 'symbolFinvasia'
        if brokerId == 0:
            brokerId = self.BrokerId

        if brokerId == Broker.FINVASIA:
            fieldName = 'symbolFinvasia'
        
        return fieldName
    
    def syncSymbols(self):
        self.syncNSEBSESymbols('NSE')
        self.syncNSEBSESymbols('BSE')
        self.syncNFOMCXSymbols('MCX')
        self.syncNFOMCXSymbols('NFO')
        self.syncCDSSymbols()
        # return True
    
    def syncNSEBSESymbols(self, exchange='NSE'):
        try:
            lstNew = []
            fieldName = self.getSymbolField()        
            scripts = Scripts.objects.filter(exchSeg = exchange)
            if self.BrokerId == Broker.FINVASIA:
                df = pd.read_csv(FINVASIA_SYMBOLS_NSE_PATH.get(exchange))

            
            for index, row in df.iterrows(): 
                if not scripts.filter(token = row['Token']).exists():
                    new = Scripts(
                    token           = row['Token'],
                    symbol          = row['TradingSymbol'],
                    name            = row['Symbol'],
                    expiry          = None,
                    strike          = 0,
                    lotSize         = row['LotSize'],
                    instrumentType  = row['Instrument'],
                    exchSeg         = row['Exchange'], 
                    segment         = row['Exchange'], 
                    tickSize        = row['TickSize'],                    
                    )
                    setattr(new, fieldName, row['TradingSymbol']) #Assign broker specific field value 
                    lstNew.append(new)
            if len(lstNew) > 0:
                Scripts.objects.bulk_create(lstNew)
        except Exception as ex:
            print(str(ex))

    def syncNFOMCXSymbols(self, exchange='NFO'):
        try:
            lstNew = []
            fieldName = self.getSymbolField()        
            scripts = Scripts.objects.filter(exchSeg = exchange)
            if self.BrokerId == Broker.FINVASIA:
                df = pd.read_csv(FINVASIA_SYMBOLS_NSE_PATH.get(exchange))

            
            for index, row in df.iterrows(): 
                # Exchange,Token,LotSize,Symbol,TradingSymbol,Expiry,Instrument,OptionType,StrikePrice,TickSize
                if not scripts.filter(token = row['Token']).exists():
                    new = Scripts(
                    token           = row['Token'],
                    symbol          = row['TradingSymbol'],
                    name            = row['Symbol'],
                    expiry          = row['Expiry'],
                    strike          = row['StrikePrice'],
                    lotSize         = row['LotSize'],
                    instrumentType  = row['Instrument'],
                    exchSeg         = row['Exchange'], 
                    segment         = row['Exchange'], 
                    tickSize        = row['TickSize'],                    
                    optionType      = row['OptionType'],                    

                    )
                    if exchange == 'MCX':
                        new.GNGD = row['GNGD']
                    setattr(new, fieldName, row['TradingSymbol']) #Assign broker specific field value 
                    lstNew.append(new)
            if len(lstNew) > 0:
                Scripts.objects.bulk_create(lstNew)
        except Exception as ex:
            print(str(ex))

    def syncCDSSymbols(self):
        try:
            exchange = 'CDS'
            lstNew = []
            fieldName = self.getSymbolField()        
            scripts = Scripts.objects.filter(exchSeg = exchange)
            if self.BrokerId == Broker.FINVASIA:
                df = pd.read_csv(FINVASIA_SYMBOLS_NSE_PATH.get(exchange))

            
            for index, row in df.iterrows(): 
                # if row['TradingSymbol'] != 'USDJPY27DEC23C124':
                #     continue
                # Exchange,Token,LotSize,Symbol,TradingSymbol,Expiry,Instrument,OptionType,StrikePrice,TickSize
                # Exchange,Token,LotSize,Precision,Multiplier,Symbol,TradingSymbol,Expiry,Instrument,OptionType,StrikePrice,TickSize,
                if not scripts.filter(token = row['Token']).exists():
                    new = Scripts(
                    token           = row['Token'],
                    symbol          = row['TradingSymbol'],
                    name            = row['Symbol'],
                    expiry          = nvl(row['Expiry'], str, '01-JAN-1900'),
                    strike          = nvl(row['StrikePrice'],numbers.Number, 0),
                    lotSize         = row['LotSize'],
                    instrumentType  = row['Instrument'],
                    exchSeg         = row['Exchange'], 
                    segment         = row['Exchange'], 
                    tickSize        = nvl(row['TickSize'], numbers.Number ,0),                    
                    optionType      = nvl(row['OptionType'],str,''),                    
                    precision       = row['Precision'],
                    multiplier      = row['Multiplier'],                    
                    )
                    setattr(new, fieldName, row['TradingSymbol']) #Assign broker specific field value 
                    lstNew.append(new)
            if len(lstNew) > 0:
                Scripts.objects.bulk_create(lstNew)
        except Exception as ex:
            print(str(ex))

def nvl(value, datatype, default=0):
    try:        
        
        if datatype in [numbers.Number, decimal.Decimal, float]:
            if isnan(value): 
                return default
            else:
                return value
        else:
            if isinstance(value,datatype):
                return value
            else:
                return default
    except Exception as ex:
        print(str(ex))
    
