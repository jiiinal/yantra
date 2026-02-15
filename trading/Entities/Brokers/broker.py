import importlib
import logging
from datetime import datetime, time
from functools import lru_cache
from time import sleep

import pandas as pd
import pytz
from django.db.models import Q

from trading.Entities.Exchanges.india import Exchange
from trading.models import Brokers
from trading.models import Scripts, MarketSessions
from utils.cachesettings import CACHE_SETTINGS, get_ttl_hash
from utils.views import isBlankOrNone

logger = logging.getLogger(__name__)

from django.db.models import F

BROKERS = {1: 'ANGEL', 2: 'ZERODHA', 3: 'FINVASIA', 4: 'FYERS', 5: 'BNRATHI', 6: 'ALICEBLUE'}
EXCHANGE_SESSIONS = {
    # 'BSE': [(time(9, 0, 0), time(9, 6, 0)), (time(9, 15, 0), time(15, 30, 0))],
    # 'NSE': [(time(9, 0, 0), time(9, 6, 0)), (time(9, 15, 0), time(15, 30, 0))],
    'BSE': [(time(9, 15, 0), time(15, 30, 0))],
    'NSE': [(time(9, 15, 0), time(15, 30, 0))],
    'CDS': [(time(9, 0, 0), time(17, 0, 0))],
    'MCX': [(time(9, 0, 0), time(23, 55, 0))],
}


class Broker():
    ANGEL = 1
    ZERODHA = 2
    FINVASIA = 3
    FYERS = 4
    BNRATHI = 5
    ALICEBLUE = 6

    def __init__(self, brokerId) -> None:
        self.BrokerId = brokerId

    @lru_cache(maxsize=4)
    def getMarketSessions(self, exchange, TTLHash=get_ttl_hash(CACHE_SETTINGS.REFRESH_CACHE_DAILY)):
        del TTLHash

        qFilter = Q(broker__brokerId=self.BrokerId, exchange__code=exchange)
        sessions = MarketSessions.objects.filter(qFilter)
        if sessions:
            marketSessions = [(session.startTime, session.EndTime) for session in sessions]
            return marketSessions
        else:
            exchange = Exchange(exchange)
            marketSessions = exchange.getMarketSessions()
            if marketSessions:
                return marketSessions
            else:
                marketSessions = EXCHANGE_SESSIONS.get(exchange.Exchange)
                return marketSessions

    def getQueueId(self, type, userid, function):
        '''
        example of the queue id is MQ1O - messge of Q, 1 is user id and O is for order function
        QueueId is generated using type user id and function
        type can be Q-Queue or A-channel to send Reply (optional, not every message have reply.) 
                    A channel is used to send reply to special messages like SUICIDE. such case reply can be send for success or error
        function -  O - for Order 
                    T - for Price update
        '''
        QueueId = f'M{type}{str(userid)}{function}'
        if type not in ['Q', 'A']:
            QueueId = None
        if function not in ['O', 'T']:
            QueueId = None

        return QueueId

    @staticmethod
    def getBrokerInstance(brokerId, accountId):
        instance = None
        try:
            broker = Brokers.objects.filter(brokerId=brokerId).first()
            if broker:
                module = importlib.import_module('trading.Entities.Brokers.' + broker.className.lower())
                class_ = getattr(module, broker.className)
                instance = class_(brokerId, accountId)
        except Exception as e:
            logger.debug(e)
        finally:
            return instance

    # @property
    def canPlaceOrder(self, exchSeg='MCX', wait=60, count=15):
        return True

        if wait > 0:
            count += 1

        MarketOpen = False

        sessions = self.getMarketSessions(exchSeg)
        while count:
            currDate = datetime.now(pytz.timezone('Asia/Kolkata'))
            currTime = currDate.time()
            for session in sessions:
                if currTime >= session[0] and currTime <= session[1] and currDate.weekday() < 6:
                    MarketOpen = True
                    count = 0
                    break
            if count > 0:
                sleep(wait)
                count -= 1
        return MarketOpen

    def isMarketOpen(self, exchSeg='NSE', wait=60, count=15):
        return True
        # exchange = Exchange(exchSeg)
        if wait > 0:
            count += 1
        sessions = self.getMarketSessions(exchSeg)

        while count:

            currDate = datetime.now(pytz.timezone('Asia/Kolkata'))
            currTime = currDate.time()
            startTime = sessions[0][0]
            endTime = sessions[-1][1]

            if currTime >= startTime and currTime <= endTime and currDate.weekday() < 6:
                return True
            else:
                if count > 0:
                    sleep(wait)
                    count -= 1
                else:
                    return False

    @lru_cache(maxsize=64)
    def getScriptByExchange(self, exchSeg, TTLHash=get_ttl_hash(CACHE_SETTINGS.REFRESH_CACHE_DAILY)):
        '''
        Get scripts as per the broker based on exchange.
        Returns only token and symbol fields for frontend.
        '''
        del TTLHash

        if not exchSeg:
            return None

        symbol_field = 'symbolFinvasia' if self.BrokerId in [self.BNRATHI, self.FINVASIA] else 'symbol'

        # Get only the 2 fields frontend needs
        symbols = Scripts.objects.filter(exchSeg=exchSeg).values('token', symbol_field)

        # Quick rename to 'symbol' for frontend compatibility
        return [
            {'token': item['token'], 'symbol': item[symbol_field]}
            for item in symbols
        ]

    @lru_cache(maxsize=64)
    def getScript(self, exchSeg, token, symbol=None, TTLHash=get_ttl_hash(CACHE_SETTINGS.REFRESH_CACHE_DAILY)):
        ''' get script as per the broker. 
        1. either token or symbol is to be provided
        2. if script is searched by both, token will get the preference
        3. if searched by symbol, broker id should be Non Zero
        For all invalid case None is returned instead of raising error 
        '''

        del TTLHash
        if isBlankOrNone(token) and isBlankOrNone(symbol):
            return None

        if not isBlankOrNone(token) and isBlankOrNone(symbol) == False:
            symbol = None

        if not isBlankOrNone(symbol) and self.BrokerId == 0:
            return None

        qFilter = Q(exchSeg=exchSeg)
        if not isBlankOrNone(symbol):
            if self.BrokerId in [self.FINVASIA, self.BNRATHI]:
                qFilter &= Q(symbolFinvasia=symbol)

        if not isBlankOrNone(token):
            qFilter &= Q(token=token)

        script = Scripts.objects.filter(qFilter).first()
        if self.BrokerId in [self.BNRATHI, self.FINVASIA]:
            script.symbol = script.symbolFinvasia

        return script

    def getRolloverScripts(self, exchSeg, token, symbol=None):
        try:
            ROLL_DAYS = {'MCX': 15, 'NSE': 5, 'BSE': 5, 'CDS': 5}
            curr = self.getScript(exchSeg, token, symbol)
            expdate = datetime.strptime(curr.expiry, "%d-%b-%Y").date()
            nexts = Scripts.objects.filter(name=curr.name, lotSize=curr.lotSize)
            ds = pd.DataFrame(list(nexts.values()))
            ds['expiry'] = pd.to_datetime(ds['expiry']).dt.date
            ds1 = ds.loc[ds['expiry'] > expdate]
            if not ds1.empty:
                return {'token': ds1.iloc[0].token, 'symbol': ds1.iloc[0].symbol, 'rollDays': ROLL_DAYS.get(exchSeg)}
            else:
                return None
        except Exception as e:
            return None

    def VerboseOrder(
            self, variety, exchange, token, symbol, tranType, priceType, prodType, price, quantity,
            disclQty, validity='DAY', stopPrice=0, stopLoss=0, takeProfit=0, orderId='',
            orderCategory='Normal', gttBuyBuffer=0, gttSellBuffer=0):
        # script = self.getScript(exchange,symbol,token)
        tsymb = symbol
        # script = getScriptBySymbol(exchange, symbol, self.brokerId, token)
        script = Scripts.objects.filter(exchSeg=exchange, token=token).first()
        if script == None:
            return None

        if exchange == 'CDS' and prodType == 'DELIVERY':
            prodType = 'MARGIN'
            if self.BrokerId in [Broker.FINVASIA, Broker.BNRATHI]:
                tsymb = script.symbolFinvasia
            else:
                tsymb = script.symbolFyers
        else:
            tsymb = script.symbol
        if priceType == 'MARKET':
            price = 0

        lstVerbose = []
        order = {
            "orderId": orderId,
            "variety": variety,
            "exchSeg": exchange,
            "symbol": tsymb,
            "token": script.token,
            "tranType": tranType,
            "priceType": priceType,
            "productType": prodType,
            "price": round(price, 2),
            "quantity": quantity,
            "stopLoss": round(stopLoss, 2),
            "validity": validity,
            "stopPrice": round(stopPrice, 2),
            "takeProfit": round(takeProfit, 2),
            "disclosedQty": disclQty,
            "orderCategory": orderCategory,
            "gttBuyBuffer": gttBuyBuffer,
            "gttSellBuffer": gttSellBuffer
        }
        lstVerbose.append(order)
        return lstVerbose
