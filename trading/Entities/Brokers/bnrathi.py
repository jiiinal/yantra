# -*- coding: utf-8 -*-
"""
Created on Sun Sep 25 2022

@author: Janisar Munshi
"""
import logging
# from ..NorenRestApiPy import NorenApi
from trading.NorenRestApiPy.api_helper import NorenApiPy, Order
# from api_helper import NorenApiPy
# from trading.views.Broker import BrokerAccount
# from trading.views.Strategies.strategy1 import Strategy1
from trading.Entities.Brokers.broker import Broker
from trading.models import Scripts, BrokerAccounts
from utils.views import isBlankOrNone, getStructKey
import pyotp
# from trading.views.strategies.Strategy import Strategy
# from trading.views.strategies.strategyTasks import processOrderUpdate, processTickUpdate

import redis

import time, threading
from datetime import datetime
from celery import shared_task
# from mainapp.views.redis import Redis
# from trading.views.Redis.rabbitMQ import RabbitMQ
from trading.Redis.pubsub import PubSub
from trading.views.utils import getBrokerAccount

import logging
logger = logging.getLogger(__name__)

# from trading.views.cacheRoutines import getScriptBySymbol
socket_opened = False

STATUS = {    
    'COMPLETE'  : 'COMPLETE',
    'REJECTED'  : 'REJECTED',
    'CANCELED'  : 'CANCELED',
    'PENDING'   : 'OPEN',
    'OPEN'      : 'OPEN',
    'PARTIAL'   : 'PARTIAL'
}

VARIETY = {
    'No'        : 'NORMAL',
    'Yes'       : 'AMO'
} 

TRAN_TYPE = {
    'B': 'BUY',
    'S': 'SELL'
}

PRICE_TYPE = {
    'LMT'       : 'LIMIT',
    'MKT'	    : 'MARKET',
    'SL-LMT'    : 'SL-LIMIT', 
    'SL-MKT'    : 'SL-MARKET'

}

VALIDITY = {
    'DAY'   : 'DAY',
    'IOC'   : 'IOC',
    'EOS'   : 'EOS',
    'GTT'   : 'GTT'
}

PRODUCT_TYPE = {
    'I'     : 'INTRADAY',
    'C'     : 'DELIVERY',
    'H'     : 'CO',
    'BO'    : 'BO',
    'M'     : 'NORMAL',
    'M'     : 'MARGIN'
}

SEGMENT_TYPE = {
    'CASH'  : 'Equity',
    'FO'    : 'Derivative',
    'COM'	: 'Commodity',
    'CUR'	: 'Currency',
    'ALL'	: 'ALL'
}

EXCHNAGE_MAP = {
    'NSE': 'NSE',
    'MCX': 'MCX',
    'BSE': 'BSE',
    'CDS': 'CDS'
}

ALERT_TYPE_ABOVE = 'LTP_A_O'
ALERT_TYPE_BELOW = 'LTP_B_O'
ALERT_TYPE_OCO = 'LTP_BOS_O'

EXCHANGE_SEGMENT = {
    'nse_cm'    :'NSE',
    'bse_cm'    :'BSE',
    'nse_fo'    :'NFO',
    'mcx_fo'    :'MCX',
    'cde_fo'    :'CDS',
    'mcx_sx'    :'BFO',
    'bcs_fo'    :'BCD',
    'nse_com'   :'NCO',
    'bse_com'   :'BCO',
}


class MSGCATEGORY():
# MESSAGES TYPES
    MANAGER = 'M0'
    ORDER = 'OR'
    TICK = 'TK'
    # MSGTYPE = [MANAGER,ORDER,TICK]

class MSGTYPE():
    INITSTRATEGY    = 'si'      # initialize strategy
    STARTSTRATEGY   = 'ss'      # start strategy
    SUBSCRIBEWS     = 'ws'      # subscribe web sockets
    SUBSCRIBECN     = 'sb'      # subscribe channel
    SUBSCRIBETK     = 'st'      # subscribe token for price change
    WAIT            = 'wt'      # ask process to wait for n seconds
    SUICIDE         = '00'
    CANCELORDERS    = 'co'      # Canel Orders

class MSGATTRIB():
    QUEUEID         = 'qId'
    CATEGORY        = 'ct'
    TYPE            = 'tp'
    TICKS           = 'tks'
    STRATEGYCODE    = 'sc'

    SUBSCRIBE       = 'sb'

    ACCOUNTID       = 'aId'
    BROKERID        = 'bId'
    ORDERID         = 'oId'
    PRODUCTTYPE     = 'ptp'
    VALIDITY        = 'vd'
    TRANTYPE        = 'ttp'
    EXCHANGE        = 'ex'
    SYMBOL          = 'sy'
    TOKEN           = 'tk'
    PRICE           = 'pr'
    LIMITPRICE      = 'lmp'
    TRADEDPRICE     = 'ltp'
    AVERAGEPRICE    = 'atp'
    PERCENTAGE      = 'prc'
    VOLUME          = 'vl'
    QTY             = 'qt'
    FILLEDQTY       = 'fqt'
    REMAINQTY       = 'rqt'
    STATUS          = 'st'
    ORDCALLBACK     = 'oc'  #Order call back - Boolean    
    WAIT            = 'wt'  # wait for N Seconds
    ORDDATETIME     = 'odt'

    OPEN            = 'o'
    HIGH            = 'h'
    LOW             = 'l'
    CLOSE           = 'c'


# from trading.views.routines import getAngelFeedToken
class BNRathi(Broker):
    def __init__(self, brokerId, accountId):                        
        super().__init__(brokerId)
        self.BrokerId  = brokerId
        self.Account = BrokerAccounts.objects.filter(id = accountId).first()
        self.ConnectionObject = None
        self.OrderQ = self.getQueueId('Q',self.Account.user.id,'O')
        self.TickQ = self.getQueueId('Q',self.Account.user.id,'T')
        # self.Redis = Redis(self.Account.user,accountId)
        # self.Queue = MessageQueue(self.Account.user.username + self.Account.clientId + 'NSE') #Dummay ID assigned
        # self.RabbitMQ = RabbitMQ('DUMMY')
        self.pubsub = PubSub()

        # self.StreamKeyTick = self.Account.user.username + '-' + str(self.Account.id) + '-' + 'T'
        # self.StreamKeyOrder = self.Account.user.username + '-' + str(self.Account.id) + '-' + 'O'
    def getTOTP(self) -> int:
        if not isBlankOrNone(self.Account.factor2Secret):
            totp = pyotp.TOTP(self.Account.factor2Secret)
            return totp.now()
        else:
            raise Exception("Not Valid TOTP can be generated")
      
    def getConnectionObject(self, sessionOnly = False):
        error = None
        if self.Account:
            # logging.basicConfig(level=logging.DEBUG)                    
            # api = NorenApi.NorenApi(
            #     host        = 'https://prime.bnrsecurities.com/NorenWClientTP/',    #'http://rama.kambala.co.in/NorenWClient/', 
            #     websocket   = 'wss://prime.bnrsecurities.com/NorenWSTP/',           #'ws://rama.kambala.co.in:5551/NorenWS/',  
            #     eodhost     = 'http://kurma.kambala.co.in/chartApi/getdata/'
            # )                        
            # passHash = hashlib.sha256(pwd.encode('utf-8')).hexdigest()
            # pwd = source.clientId + '|' + source.apiSecret
            # keyHash = hashlib.sha256(pwd.encode('utf-8')).hexdigest()
            try:
                api = NorenApiPy(self.BrokerId)  

                if isBlankOrNone(self.Account.factor2):
                    factor2 = self.getTOTP()
                else:
                    factor2 = self.Account.factor2

                if self.Account.acccessToken:
                    login = api.set_session(
                        userid = self.Account.clientId, password = self.Account.password, usertoken=self.Account.acccessToken)
                else:                    
                    login = api.login(
                        userid = self.Account.clientId, password = self.Account.password, twoFA = factor2, 
                        vendor_code = self.Account.vendorCode, api_secret = self.Account.apiKey, imei='abc1234')
                    if login:
                        self.Account.acccessToken = login.get('susertoken')
                        self.Account.save()

                try:
                    quote = None
                    quote = api.get_quotes('NSE','2885')
                    if sessionOnly:
                        self.ConnectionObject = api
                        return api
                except Exception:
                    if sessionOnly:
                        return None


                if quote is None:
                    ret = api.login(
                    userid = self.Account.clientId, password = self.Account.password, twoFA = factor2, 
                    vendor_code = self.Account.vendorCode, api_secret = self.Account.apiKey, imei='abc1234')                    

                    self.Account.acccessToken = ret.get('susertoken')
                    self.Account.save()
                    self.ConnectionObject = api
                    return api
                else:
                    self.ConnectionObject = api
                    return api                    
                    # error = {'status':400, 'message': f'connection could not be established for account:{self.Account.id}' }                                        
            except:            
                error = {'status':400, 'message': f'erro while getting connection for account:{self.Account.id}' }                    
        else:
            error = {'status':404, 'message': f'No Account with id:{self.Account.id}' }

        self.Errors = error
        return self.ConnectionObject

    def closeWebSocket(self, ws):
        try:
            if ws is None:
                ws = self.connection.get('Connection')
            ws.close_websocket()
            return True
        except:
            return False
    def formatOrderCallback(self, message) -> dict:
        order = {}
        script = self.getScript(message.get('exch'),'',message.get('tsym'))
        if script:
            order = {
                'QueueId'       : self.OrderQ,
                'accountId'     : message.get('aId'),
                'orderId'       : message.get('norenordno'),
                'productType'   : PRODUCT_TYPE.get(message.get('pcode')),
                'validity'      : VALIDITY.get(message.get('ret')),
                'tranType'      : TRAN_TYPE.get(message.get('trantype')),
                'exchSeg'       : message.get('exch'),
                'symbol'        : message.get('tsym'),
                'token'         : script.token,
                'limitPrice'    : message.get('prc'),
                'tradePrice'    : message.get('avgprc'),
                'qty'           : message.get('qty'),
                'remQty'        : 0,
                'filledQty'     : message.get('qty'),
                'status'        : STATUS.get(message.get('status')), 
                'ordDateTime'   : message.get('exch_tm')
            }        
        else:
            logger.error(f"Script not found for Exchange{message.get('exch')} token {message.get('tsym')}") 

        return order
            
    def formatTickCallback(self,accountId, message) -> dict:
        ba = getBrokerAccount(accountId)
        script = self.getScript(message.get('exch'),'',message.get('tsym')) 
        tick = {
            MSGATTRIB.CATEGORY      : MSGCATEGORY.TICK,            
            MSGATTRIB.ACCOUNTID     : accountId,
            MSGATTRIB.EXCHANGE      : message.get('e',''),
            MSGATTRIB.TOKEN         : message.get('tk',''),
            MSGATTRIB.SYMBOL        : script.symbolFinvasia,
            MSGATTRIB.TRADEDPRICE   : message.get('lp',0),
            MSGATTRIB.PERCENTAGE    : message.get('pc',0),
            MSGATTRIB.VOLUME        : message.get('v',0),
            MSGATTRIB.OPEN          : message.get('o',0),
            MSGATTRIB.HIGH          : message.get('h',0), 
            MSGATTRIB.LOW           : message.get('l',0), 
            MSGATTRIB.CLOSE         : message.get('c',0),
            MSGATTRIB.AVERAGEPRICE  : message.get('ap',0),
        }
        return tick    



        
    def subscribeWebSockets(self, orderCallback = True, lstTicks = []):
        
        
        def event_handler_order_update(message):
            identifier = {
                'MTYPE': 'ORD',
                'QID': self.OrderQ,
                MSGATTRIB.ACCOUNTID: self.Account.id
            }
            message.update(identifier)
            self.pubsub.publish(self.OrderQ, message)
            

        def event_handler_Tick_update(message):
            if float(message.get('lp',0)) > 0:

                message.update({MSGATTRIB.ACCOUNTID: self.Account.id})
                self.pubsub.publish(self.TickQ, message)

        def open_callback():
            global socket_opened
            lstSubsribe = []
            for script in lstTicks:
                lstSubsribe.append(f"{script['exchange']}|{script['token']}")

            if len(lstSubsribe) > 0:
                self.ConnectionObject.subscribe(lstSubsribe)            

            socket_opened = True            

        r = self.pubsub.Redis
        lock = r.setnx(f'WS{self.Account.id}', 'running')
        if lock:
            r.expire(f'WS{self.Account.id}', 10)  # auto-expire after an hour

            if orderCallback:
                self.ws = self.ConnectionObject.start_websocket(
                    order_update_callback   = event_handler_order_update,     
                    subscribe_callback      = event_handler_Tick_update,         
                    socket_open_callback    = open_callback 
                    )  
                logger.debug(f'order and tick subscribed for {self.Account.nickName}:{self.Account.clientId}')
            else:
                self.ws = self.ConnectionObject.start_websocket(
                    subscribe_callback      = event_handler_Tick_update,         
                    socket_open_callback    = open_callback 
                    )  
                logger.debug(f'tick subscribed for {self.Account.nickName}:{self.Account.clientId}')

        else:
            logger.debug(f"WebSocket already running for account {self.Account.nickName}. Skipping.")


    def readOrderBook(self, orderId='', OrderCatagory = 'All'):
        # OrderCatagory = 'All', 'GTT','Normal'

        conn = self.ConnectionObject
        lstOrders = []    
        if OrderCatagory in ['GTT','All']:
            orders = conn.get_pending_gtt_orders()
            if orders:
                for ord in orders:
                    if ord['stat'] != 'Ok':
                        continue
                    if not isBlankOrNone(orderId) and ord.get('al_id','norenordno') != orderId:
                        continue
                    exchange = ord.get('exch')
                    symbol = ord.get('tsym')
                    # script = Scripts.objects.filter(exchSeg = exchange, symbol = symbol).first()

                    Order = {
                        "sourceAccountId"   : self.account.id,
                        "brokerId"          : self.connection['brokerId'],
                        "variety"           : VARIETY.get('No'),
                        "priceType"         : PRICE_TYPE.get(ord.get('place_order_params').get('prctyp')),
                        # "orderType"         : TRAN_TYPE.GET(ord['Trantype']),
                        "productType"       : PRODUCT_TYPE.get(ord.get('place_order_params').get('prd')),
                        "duration"          : VALIDITY.get('GTT'), # DAY / IOC
                        "averagePrice"      : ord.get('place_order_params').get('prc',0),
                        "triggerPrice"      : ord.get('place_order_params').get('d',0),
                        "quantity"          : int(ord.get('place_order_params').get('qty')),
                        "disclosedQuantity" : 0,
                        "squareOff"         : 0, #ord['squareoff']
                        "stopLoss"          : 0,
                        "trailingStopLoss"  : 0, #ord['trailingstoploss'],
                        "symbol"            : ord.get('tsym'),
                        "tranType"          : TRAN_TYPE.get(ord['trantype']),
                        "exchange"          : ord.get('exch'),
                        "token"             : ord.get('token',''),
                        "orderTag"          : None, #ord['remarks'],
                        "instrumentType"    : '',
                        "strikePrice"       : None, #ord['strikePrice'],
                        "optionType"        : None, #For Option trading BC-Buy Call, SC - Sell Call, BP - Buy Put, SP - Sell Put
                        "expiryDate"        : None, #ord['expirydate'],
                        "lotSize"           : None, #ord['lotsize'],
                        "cancelSize"        : None, #ord['cancelsize'],                        
                        "filledShares"      : 0,
                        "unfilledShares"    : int(ord.get('place_order_params').get('qty')), 
                        "orderId"           : ord['al_id'],
                        "text"              : None,
                        "status"            : STATUS.get('OPEN'),
                        "orderStatus"       : STATUS.get('OPEN'), #ord['orderstatus'],
                        "OrderedTime"       : ord.get('norentm','exch_tm'), #'19:59:32 13-12-2020'
                        "ExecutionTime"     : None,
                        # "parentOrderId"     : ord['parentorderid'],
                        "sourceOrderId"     : None
                    }
                    lstOrders.append(Order)

        if OrderCatagory in ['Normal','All']:
            if isBlankOrNone(orderId):
                orders = conn.get_order_book()
            else:
                orders = conn.single_order_history(orderno=orderId)

            if orders:
                for ord in orders:
                    if ord['stat'] != 'Ok':
                        continue
                    exchange = ord.get('exch')
                    symbol = ord.get('tsym')
                    # script = Scripts.objects.filter(exchSeg = exchange, symbol = symbol).first()

                    Order = {
                        "sourceAccountId"   : self.Account.id,
                        "brokerId"          : self.BrokerId,
                        "variety"           : VARIETY.get(ord.get('amo')),
                        "priceType"         : PRICE_TYPE.get(ord['prctyp']),
                        # "orderType"         : TRAN_TYPE.GET(ord['Trantype']),
                        "productType"       : PRODUCT_TYPE.get(ord['prd']),
                        "duration"          : VALIDITY.get(ord['ret']), # DAY / IOC
                        "averagePrice"      : ord.get('avgprc',0),
                        "triggerPrice"      : ord.get('trgprc',0),
                        "quantity"          : int(ord['qty']),
                        "disclosedQuantity" : ord.get('dscqty'),
                        "squareOff"         : 0, #ord['squareoff']
                        "stopLoss"          : ord.get('blprc',0),
                        "trailingStopLoss"  : 0, #ord['trailingstoploss'],
                        "symbol"            : ord.get('tsym'),
                        "tranType"          : TRAN_TYPE.get(ord['trantype']),
                        "exchange"          : ord.get('exch'),
                        "token"             : ord.get('token',''),
                        "orderTag"          : None, #ord['remarks'],
                        "instrumentType"    : '',
                        "strikePrice"       : None, #ord['strikePrice'],
                        "optionType"        : None, #For Option trading BC-Buy Call, SC - Sell Call, BP - Buy Put, SP - Sell Put
                        "expiryDate"        : None, #ord['expirydate'],
                        "lotSize"           : None, #ord['lotsize'],
                        "cancelSize"        : None, #ord['cancelsize'],                        
                        "filledShares"      : 0,
                        "unfilledShares"    : int(ord['qty']) , 
                        "orderId"           : ord['norenordno'],
                        "text"              : None,
                        "status"            : STATUS.get(ord['status']),
                        "orderStatus"       : STATUS.get(ord['status']), #ord['orderstatus'],
                        "OrderedTime"       : ord['norentm'], #'19:59:32 13-12-2020'
                        "ExecutionTime"     : None,
                        # "parentOrderId"     : ord['parentorderid'],
                        "sourceOrderId"     : None
                    }
                    lstOrders.append(Order)
        self.orders = lstOrders
        return lstOrders        
    
    def getPositions(self):
        conn = self.ConnectionObject
        positions = conn.get_positions()         
        return positions
    
    def readTradeBook(self, orderId=''):
        conn = self.ConnectionObject
        lstOrders = []
        Orders = conn.get_trade_book() 

        for ord in Orders:
            if ord.get('stat') != 'Ok':
                continue
            order = {                
                "sourceAccountId"   : self.Account.id,
                "brokerId"          : self.Account.broker_id,
                "exchange"          : ord.get('exch'),
                "token"             : ord.get('token'),
                "producttype"       : PRODUCT_TYPE.get(ord.get('prd')), 
                "priceType"         : PRICE_TYPE.get(ord.get('prctyp')),
                "tradingsymbol"     : ord.get('tsym'),
                "instrumenttype"    : "",
                "symbolgroup"       : None, 
                "strikeprice"       : float(ord.get('prc')),
                "optiontype"        : "",
                "expirydate"        : "",
                "marketlot"         : ord.get('ls'),
                "precision"         : ord.get('pp'), 
                "multiplier"        : None,
                "tradevalue"        : float(ord.get('flprc')) * float(ord.get('flqty')), 
                "tranType"          : TRAN_TYPE.get(ord.get('trantype')),
                "fillprice"         : float(ord.get('flprc')),
                "fillsize"          : int(ord.get('flqty')),
                "orderid"           : ord.get('norenordno'),
                "fillid"            : ord.get('flid'),
                "filltime"          : ord.get('fltm')
            }            
            lstOrders.append(order)
        return lstOrders

    def prepareOrderParams(self, action, verboseOrder):                
        if type(verboseOrder) != list:
            return None

        orderParams = []
        for order in verboseOrder:
            if order['exchSeg'] == 'CDS':
                broker = Broker(self.BrokerId)
                # script = Scripts.objects.filter(exchSeg = exchange, symbol = order['symbol']).first()
                script = broker.getScript(order['exchSeg'], order['token'], order['symbol'])
                if script:
                    symbol = order['symbol']                     
                else:
                    continue
            else:
                symbol = order['symbol']
            exchange = EXCHNAGE_MAP.get(order['exchSeg'])
            if order['priceType'] == 'MARKET':
                order['price'] = 0            
            
            # token         = order['token']
            quantity        = order['quantity']
            priceType       = order['priceType']
            tranType        = order['tranType']
            prodType        = order['productType']
            price           = order['price']
            stopLoss        = order['stopLoss']
            stopPrice       = order['stopPrice']
            disclQty        = order['disclosedQty']
            offlineOrder    = getStructKey(VARIETY,order['variety'])
            validity        = order['validity']
            # takeProfit      = order['takeProfit']
            orderId         = order.get('orderId')
            isGTT           = order.get('isGTT')
            gttBuyBuffer    = order.get('gttBuyBuffer', 0) 
            gttSellBuffer   = order.get('gttSellBuffer', 0)

            if action.upper()  in ['NEW','CREATE']:   
                if isGTT:
                    param = {
                        "tradingsymbol"   : symbol,
                        "exchange"        : exchange,
                        "alert_type"      : ALERT_TYPE_BELOW if tranType == 'BUY' else ALERT_TYPE_ABOVE, # 'LTP_A_O' or 'LTP_B_O'
                        "alert_price"     : price - ( float(gttBuyBuffer) if tranType == 'BUY' else float(gttSellBuffer * -1)),
                        "buy_or_sell"     : getStructKey(TRAN_TYPE, tranType), # 'B' or 'S'
                        "product_type"    : getStructKey(PRODUCT_TYPE, prodType), # 'I' Intraday, 'C' Delivery, 'M' Normal Margin for options
                        "quantity"        : quantity,
                        "price_type"      : getStructKey(PRICE_TYPE,priceType), #'MKT',
                        "price"           : 0.0,
                        "remarks"         : None,
                        "retention"       : validity, #'DAY',
                        "validity"        : 'GTT',
                        "discloseqty"     :0                    
                        }                  

                else:
                    param = {
                        "amo"           : VARIETY.get(order.get('variety')),
                        "buy_or_sell"   : getStructKey(TRAN_TYPE, tranType),
                        "product_type"  : getStructKey(PRODUCT_TYPE, prodType),
                        "exchange"      : exchange,
                        "tradingsymbol" : symbol,
                        "quantity"      : quantity,
                        "discloseqty"   : disclQty,
                        "price_type"    : getStructKey(PRICE_TYPE,priceType),
                        "price"         : price,
                        "trigger_price" : None,
                        "retention"     : validity,
                        "remarks"       : ''
                        }
                orderParams.append(param)

            if action.upper()  in ['UPDATE','MODIFY','CHANGE']:
                if orderId == '':
                    return None
                if isGTT:
                    param = {
                        "orderno"         : orderId,
                        "tradingsymbol"   : symbol,
                        "exchange"        : exchange,
                        "alert_type"      : ALERT_TYPE_BELOW if tranType == 'BUY' else ALERT_TYPE_ABOVE, # 'LTP_A_O' or 'LTP_B_O'
                        "alert_price"     : price - ( float(gttBuyBuffer) if tranType == 'BUY' else float(gttSellBuffer * -1)),
                        "buy_or_sell"     : getStructKey(TRAN_TYPE, tranType), # 'B' or 'S'
                        "product_type"    : getStructKey(PRODUCT_TYPE, prodType), # 'I' Intraday, 'C' Delivery, 'M' Normal Margin for options
                        "quantity"        : quantity,
                        "price_type"      : getStructKey(PRICE_TYPE,priceType), #'MKT',
                        "price"           : 0.0,
                        "remarks"         : None,
                        "retention"       : validity, #'DAY',
                        "validity"        : 'GTT',
                        "discloseqty"     : 0                    
                        } 
                else:                
                    param = {
                        "exchange"      : exchange,
                        "tradingsymbol" : symbol,
                        "orderno"       : orderId,
                        "newquantity"   : quantity, 
                        "newprice_type" : getStructKey(PRICE_TYPE,priceType), 
                        "newprice"      : price                   
                    }                
                orderParams.append(param)

        return orderParams


    def prepareOrderParamsOB(action, orderBook):        
        # variety = 'NORMAL' if isMarketOpen() else 'AMO'
        orderParams = []
        for order in orderBook:                               
            if action.upper()  in ['NEW','CREATE']:   
                param = {
                    "symbol"        : f"{order.get('exchange')}:{order.get('tradingSymbol')}", # "MCX:SILVERMIC20NOVFUT",
                    "qty"           : order.get('quantity'),
                    "type"          : getStructKey(PRICE_TYPE,order.get('priceType')), #FYERS_ORDTYPE_LIMIT if float(param.get('price')) > 0 else FYERS_ORDTYPE_MARKET,
                    "side"          : getStructKey(TRAN_TYPE,order.get('tranType')),
                    "productType"   : getStructKey(PRODUCT_TYPE, order.get('productType')),
                    "limitPrice"    : str(round(float(param.get('price')),2)),
                    "stopPrice"     : 0,
                    "validity"      : order.get('duration'),
                    "disclosedQty"  : 0,
                    "offlineOrder"  : 'False',
                    "stopLoss"      : param.get('stoploss'),
                    "takeProfit"    : 0
                    }
                orderParams.append(params)
            if action.upper()  in ['UPDATE','MODIFY','CHANGE']:
                params = {
                    "id":param.get('orderId'), 
                    "type" : getStructKey(PRICE_TYPE,order.get('priceType')),
                    "limitPrice": str(round(float(param.get('price')),2)),
                    "qty": order.get('quantity'),
                }                
                orderParams.append(params)

        return orderParams

    def prepareOrderParamsTB(self, action, tradeBook, priceType = 'MARKET'):        
        # variety = 'NORMAL' if isMarketOpen() else 'AMO'
        orderParams = []
        for trade in tradeBook:                               
            if action.upper()  in ['NEW','CREATE']:   

                param = {
                    "symbol"        : f"{trade.get('exchange')}:{trade.get('tradingSymbol')}", # "MCX:SILVERMIC20NOVFUT",
                    "qty"           : trade.get('fillSize'),
                    "type"          : getStructKey(PRICE_TYPE, priceType) if priceType != '' else getStructKey(PRICE_TYPE,trade.get('priceType')), #FYERS_ORDTYPE_LIMIT if float(param.get('price')) > 0 else FYERS_ORDTYPE_MARKET,
                    "side"          : getStructKey(TRAN_TYPE, trade.get('tranType')),
                    "productType"   : getStructKey(PRODUCT_TYPE, trade.get('productType')),
                    "limitPrice"    : str(round(float(trade.get('fillPrice')),2)),
                    "stopPrice"     : 0,
                    "validity"      : trade.get('duration'),
                    "disclosedQty"  : 0,
                    "offlineOrder"  : 'False',
                    "stopLoss"      : trade.get('stoploss'),
                    "takeProfit"    : 0
                    }

                orderParams.append(params)

            if action.upper()  in ['UPDATE','MODIFY','CHANGE']:
            
                params = {
                    "id"            : param.get('orderId'), 
                    "type"          : getStructKey(PRICE_TYPE, priceType) if priceType != '' else getStructKey(PRICE_TYPE,trade.get('priceType')),
                    "limitPrice"    : str(round(float(trade.get('fillPrice')),2)),
                    "qty"           : trade.get('fillSize'),
                }           
                orderParams.append(params)

        return orderParams


    def createOrders(self, orderParams):
        # if self.connection == None:
        #     return None
        # if self.connection['status'] == 200:
        #     conn = self.connection['Connection']
        # else:
        #     return None
        lstNewOrd = []
        if len(orderParams) == 1:
            param = orderParams[0]
            isGTT = param.get('validity') == 'GTT'
            if isGTT:
                param['price_type'] = 'MKT'
                response = self.ConnectionObject.place_gtt_order(**param)
                response = {'norenordno': response}
            else:
                order = Order(
                    param.get('buy_or_sell'),param.get('product_type'),param.get('exchange'),
                    param.get('tradingsymbol'),param.get('price_type'), param.get('quantity'),
                    param.get('price'), param.get('trigger_price'), param.get('discloseqty'),
                    param.get('retention'), param.get('remarks'), param.get('order_id','')
                )

                response = self.ConnectionObject.place_order(order)

            if response.get('norenordno','') != '':
                created = {
                    'orderId'   : response['norenordno'],
                    'message'   : 'created',
                    'status'    : 'ok'
                }
            else:
                created = {
                    'orderId'   : None,
                    'message'   : response.get('emsg'),
                    'status'    : 'err'
                }

            lstNewOrd.append(created)

        else:
            # **************** Not modified yet - this needs to be implemented below code is a sample code ***********************************
            response = self.ConnectionObject.place_basket_orders(**orderParams)
            if response.get('s') == 'ok':
                orderData = response.get('data')
                for data in orderData:
                    created = {
                        'orderId'   : data.get('body').get('id'),
                        'message'   : data.get('body').get('message'),
                        'status'    : data.get('body').get('s') 
                    }
                lstNewOrd.append(created)

        return lstNewOrd            

    def modifyOrders(self, orderParams):
        # if self.connection == None:
        #     return None
        # if self.connection['status'] == 200:
        #     conn = self.connection['Connection']
        # else:
        #     return None
        
        lstModified = []
        if len(orderParams) == 1:
            params = orderParams[0]
            isGTT = params.get('validity') == 'GTT'
            if isGTT:
                self.ConnectionObject.cancel_gtt_order(params.get('orderno'))
                params.pop("orderno")
                response = self.ConnectionObject.place_gtt_order(**params)
                response = {'norenordno': response}                
            else:
                response = self.ConnectionObject.modify_order(**params)
                if response.get('stat') == "Ok":
                    modified = {
                        'orderId'   : params.get('orderno'),
                        'message'   : response.get('result'),
                        'status'    : response.get('stat'),
                    }                
                else:
                    modified = {
                        'orderId'   : params.get('orderno'),
                        'message'   : response.get('emsg'),
                        'status'    : 'err',
                    }

                lstModified.append(modified)
        else:            

            # **************** Not modified yet - this needs to be implemented below code is a sample code ***********************************
            response = self.ConnectionObject.modify_basket_orders(**orderParams)
            if response.get('s') == 'ok':
                orderData = response.get('data')
                for data in orderData:
                    modified = {
                        'ordderId'  : data.get('body').get('id'),
                        'message'   : data.get('body').get('message'),
                        'status'    : data.get('body').get('s') 
                    }
                    lstModified.append(modified)   

        return lstModified   

    def cancelOrders(self, orders:list=[], exchange=None):
        try:
            orderBook = self.readOrderBook('','Normal')
            if not orderBook:
                return False
            
            for order in orderBook:
                if order.get('status') == 'OPEN' and (order.get('orderId') in orders or orders == []): 
                    if exchange and order.get('exchange') != exchange:
                        continue
                    self.ConnectionObject.cancel_order(order.get('orderId'))

            return True
        except Exception as e:
            print(str(e))
        finally:
            return True



    def getHistoricalData(self, exchSeg, symbol, token, fromdate, todate, interval="DAY"): 
        # if self.connection == None:
        #     return None
        # if self.connection['status'] == 200:
        #     conn = self.connection['Connection']
        # else:
        #     return None        
        if interval == 'DAY':
            interval = 240
        # fdate = fromdate.strftime('%Y-%m-%d')
        # tdate = todate.strftime('%Y-%m-%d') 
        fdate = fromdate.strftime("%d/%m/%Y")
        tdate = todate.strftime("%d/%m/%Y")

        fdate = time.mktime(datetime.strptime(fdate, "%d/%m/%Y").timetuple())
        tdate = time.mktime(datetime.strptime(tdate, "%d/%m/%Y").timetuple())

        data = reversed(self.ConnectionObject.get_time_price_series(exchSeg, token, fdate, tdate, interval= interval))
        candleData = [
                 {
                    'exchSeg'   : exchSeg,
                    'symbol'    : symbol,
                    'token'     : token,
                    'histDate'  : datetime.strptime(item['time'], '%d-%m-%Y %H:%M:%S'),
                    'open'      : item['into'],
                    'high'      : item['inth'],
                    'low'       : item['intl'],
                    'close'     : item['intc'],
                    'volume'    : item['intv']                    
                 } for item in data
            ]
        return candleData

    def getHoldings(self, product_type=None):
        return self.ConnectionObject.get_holdings(product_type)