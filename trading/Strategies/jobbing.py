import traceback

from trading.models import JobbingSettings, StrategyStatus, Strategis, JobbingLog
from social.views.telegram import Telegram
# from trading.views.Entities.brokerAccount import BrokerAccount
from trading.Strategies.strategy import Strategy
import pandas as pd
from utils.views import isBlankOrNone, convertUTCtoIST

from celery import shared_task

# from mainapp.views.utils import pdSeries
from datetime import datetime
from threading import Thread
from trading.Entities.Brokers.broker import Broker
from trading.Entities.BrokerAccounts.brokerAccount import BrokerAccount
import pytz 
from decimal import Decimal
# from trading.views.Redis.messageQueue import MessageQueue
# from trading.views.Redis.rabbitMQ import RabbitMQ
from trading.Redis.pubsub import PubSub
from trading.Redis.pubsub import getRedisInstance
# from trading.views.Strategies.strategy import getStrategyQueueId
from social.models import UserSocialProfile
from django.contrib.auth.models import User
from trading.models import BrokerAccounts, Exchanges
from time import sleep

from django.db.models import Q
# from mainapp.views.logger import logging
# for sending Email
from io import BytesIO
import xlwt
import hashlib
from django.conf import settings
from trading.Entities.Brokers.bnrathi import MSGATTRIB

from social.views.email import EMail
from django.db import transaction
import logging
logger = logging.getLogger(__name__)

STRATEGY_CODE = 'JOBBING'



class Jobbing(Strategy):
    def __init__(self, user, exchange=None) -> None:
        self.code = STRATEGY_CODE
        self.exchange = exchange
        StrategyMaster = Strategis.objects.filter(code = self.code).first()
        self.User = user
        self.telegram = Telegram(self.User.id)
        if not StrategyMaster:
            self.telegram.sendMessage(f'Err: No strategy defined with code {self.code}')
            raise Exception(f'No strategy defined with code {self.code}')
        self.StrategyMaster = StrategyMaster
        self.isActive = StrategyMaster.isActive
        self.getActiveSetup(exchange)
        self.MasterQueue = 'DUMMY'
        self.PubSub = PubSub()

        
    def getActiveSetup(self, exchange=None):
        lstActiveAccounts = []
        lstActiveScripts = []
        self.Setups = JobbingSettings.objects.select_related().filter(user=self.User, isActive=True, target__isActive=True).order_by('target_id', 'exchange')
        if not exchange:
            exchange = self.exchange
            
        if exchange:
            self.Setups = self.Setups.filter(exchange__code=exchange)
        # self.setupFrame = pd.DataFrame(list(self.Setups.values()))
        # print(self.setupFrame)
        # broker = Broker(0)
        for setup in self.Setups:
            if setup.target.id not in lstActiveAccounts:
                lstActiveAccounts.append(setup.target.id)      

            activeScript = {
                # 'OrderQId'      : broker.getQueueId(self.User.username,setup.target.clientId,setup.exchange,'O') if self.requireOrderCallback else None,
                # 'TickQId'       : broker.getQueueId(self.User.username,setup.target.clientId,setup.exchange,'T') if self.requireTickCallback else None,
                # 'strategyCode'  : self.code,
                'accountId': setup.target.id,
                'clientId': setup.target.clientId,
                'brokerId': setup.target.broker.brokerId,
                'exchange': setup.exchange,
                'token': setup.token,
                'symbol': setup.symbol,
                # 'rolloverToken' : setup.rolloverToken if setup.rolloverActive else None,
                # 'rolloverDays'  : setup.rolloverDays if setup.rolloverActive else None
            }
            if activeScript not in lstActiveScripts:
                lstActiveScripts.append(activeScript)             

        self.ActiveAccounts = lstActiveAccounts
        self.ActiveScripts = lstActiveScripts
        return self.Setups

    def isActive(self, user = None):
        if not self.StrategyMaster.isActive: #check in the master table
            return False
        
        if not user:
            user = self.User
        
        if user == None:
            self.telegram.sendMessage(f'No user defined for strategy code {self.code}')
            raise Exception(f'No user defined for strategy code {self.code}')

        setups = self.getActiveSetup()        
        return setups != None

    def getScriptForTickCallback(self):
        # it should be in the format of {'accountId': {accountId}, 'exchange': {exchange}, 'token': {token}, 'symbol':{symbol}}
        return []
    
    def getOrders(self,status='OPEN'):
        return JobbingLog.objects.filter(status = status)
        

    @property
    def requireOrderCallback(self):
        return True

    @property
    def requireTickCallback(self):
        return False

    def getStatus(self):
        status = StrategyStatus.objects.filter(user = self.User, strategy = self.StrategyMaster).first()
        if status:
            return status.currStatus
        else:
            return None

    def setStatus(self, status):
        stat = StrategyStatus.objects.filter(user = self.User, strategy = self.StrategyMaster).first()
        if stat:
            stat.currStatus = status
        else:
            stat = StrategyStatus(
                user            = self.User,
                strategy        = self.StrategyMaster,
                currStatus      = status,                
                taskId          = ''
            )
        stat.save()

    def initiate(self,exchange=None):
        try:
            # self.getActiveSetup(exchange)
            self.setStatus('Initiated')
            self.telegram.sendMessage(f'Strategy {self.code} Initiated')
            return self.isActive

        except Exception as exc:
            print(exc)
            return False
        
    '''Rollover Functiona is postponed due to 
    1. Need more clarity what time to do the rollover
        if we rollover at the time of market open, 
            need to change token value for new trade, when ?
            what to do for open position
    2. Put market order or limit order
    3. What should be the current price set for the rollover token take LTP or other value ?
    '''
    # def rolloverToken(self, brokerAccount, exchange=None):
    #     accountId = 0
    #     for setup in self.Setups:
    #         if accountId != setup.target.id:
    #             accountId = setup.target.id
    #             brokerObj = brokerAccount.getBrokerObject(accountId)

    #         if exchange and setup.exchange != exchange:
    #             continue
            

    # def cancelPendingOrders(self, exchange=None, token=None, status = 'OPEN'):
    #     qFilter = Q(user = self.User)
    #     if exchange:
    #         qFilter &= Q(exchange = exchange)
        
    #     if token:
    #         qFilter &= Q(token = token)

    #     if status:
    #         qFilter &= Q(status = status)

    #     logs = Strategy1Log.objects.filter(qFilter)


    def start(self, brokerAccount, exchange=None):
        try:
            self.telegram.sendMessage(f'{self.code} : execution started')


            self.processOrderCallback(exchange)
            self.telegram.sendMessage(f'{self.code} : Order tracking started')

            self.processTickCallback(exchange)
            # self.telegram.sendMessage(f'{self.code} : price tracking Started if applicable')
            sleep(2)
            self.createInitialOrder(brokerAccount)
            self.telegram.sendMessage(f'{self.code} : Initial Order Placed')

        except Exception as e:
            logger.debug(f"jobbing start error {str(e)}")

    def createInitialOrder(self, brokerAccount):
        '''
        1. Identify unique borker accounts 
        2. Cancel old orders for each broker accounts
        3. Create Initial Order pair for each setup 
        '''
        lstAccIds = []
        
        for setup in self.Setups:
            if not setup.target.id in lstAccIds:
                lstAccIds.append(setup.target.id)

        for accId in lstAccIds:
            brokerObj = brokerAccount.getBrokerObject(accId)
            orders = self.getOrders('OPEN')
            if orders:
                lstOrd = [ord.orderId for ord in orders]
                brokerObj.cancelOrders(lstOrd)
                sleep(1)


        for setup in self.Setups:

            simulation = setup.simulate         
            flagReverseTick = False   
            # script = Scripts.objects.filter(exchange = setup.exchange, token = setup.token).first()

            lotSize = setup.buyLot
            lotSizeSell = setup.sellLot
            tickSize = setup.buyTick
            tickSizeSell = setup.sellTick
            '''
            remove all older un executed order from log
            '''
            JobbingLog.objects.filter(user = self.User, exchange = setup.exchange, token = setup.token).exclude(status = 'COMPLETE').delete()
            log = JobbingLog.objects.filter(user = self.User, exchange = setup.exchange, token = setup.token, status__in = ['COMPLETE','PARTIAL']).order_by('-updatedOn').first()
            if log:
                if setup.priceCurrent > 0:
                    basePrice = setup.priceCurrent
                    # setup.overridePrice = 0
                    # setup.save()
                    
                    self.telegram.sendMessage(f'{self.code} : Override Price {basePrice}')
                else:                
                    basePrice = log.price                    
                    self.telegram.sendMessage(f'{self.code} : Base Price {basePrice} as per last Transaction')

                if log.orderType == 'SELL':
                    flagReverseTick = True
                    # flagReverseTick = False
                # currStock = log.currStock
            else:            
                # currStock = setup.initialStock
                if setup.priceCurrent > 0:
                    basePrice = setup.priceCurrent            
                else:
                    basePrice = setup.priceBase
                
                self.telegram.sendMessage(f'{self.code} : no prev record, setup base price {basePrice}')

                  
            if self.getStatus() == 'TERMINATE':
                return


            buyOnly = False
            sellOnly = False 
            if setup.stockCurrent >= setup.stockMax:
                sellOnly = True                        
            if setup.stockCurrent <= setup.stockMin :                        
                buyOnly = True

            try:
                
                self.executeOrderPair(
                    self.User.id, setup.target, setup.exchange.code, setup.token, setup.dayOrders, 
                    basePrice, lotSize, tickSize, buyOnly, sellOnly, simulation, tickSizeSell, lotSizeSell, 
                    flagReverseTick, True, setup.orderCatagory, setup.gttBuyBuffer, setup.gttSellBuffer, 
                    setup.wait, setup.count
                    )

            except Exception as exc:
                # self.Telegram.sendMessage(f"Error: Inital Order Palce")
                print(exc)
                continue
                
        # self.telegram.sendMessage('Initial order placed function completed')
        

    # def processOrderCallback(self, strategy):
    #     if self.requireOrderCallback:

    #         self.setupFrame = pd.DataFrame(self.ActiveScripts)
    #         psAccount = pdSeries(self.setupFrame)
    #         for accountId in psAccount.accountId:
    #             psExchange = pdSeries(self.setupFrame,'accountId',accountId)
    #             for exchange in psExchange.exchange:
    #                 workerS1OrderCallback(strategy.code, str(accountId), exchange)
    #                 # workerS1OrderCallback.delay(strategy.code, str(accountId), exchange)
            
    #     return True

    def processOrderCallback(self, exchange=None):
        if not exchange:
            exchange = self.exchange
        if self.ActiveScripts == []:
            self.getActiveSetup(exchange)
            
        lstUnique = []
        if self.requireOrderCallback:
            for script in self.ActiveScripts:
                if exchange and script.get('exchange') != exchange:
                    continue

                dict = {
                'accountId'     : script.get('accountId'),
                'exchange'      : script.get('exchange'),
                # 'OrderQId'      : script.get('OrderQId')
                }
                

                if not dict in lstUnique:
                    lstUnique.append(dict)

            lstThreads = []
            for item in lstUnique:
                # t1 = Thread(target=workerS1OrderCallback, args=(self.code, str(item.get('accountId')), item.get('exchange').code)
                #             )
                # lstThreads.append(t1)
                workerS1OrderCallback.delay(self.code, str(item.get('accountId')), item.get('exchange').code)
                # workerS1OrderCallback(self.code, str(item.get('accountId')), item.get('exchange'), item.get('OrderQId'))
            for t1 in lstThreads:
                t1.start()
        # sleep(5)
        return True

    def processTickCallback(self, exchange=None):
        if self.requireTickCallback:            
            pass

        return True

    def getOrderLog(
            self, startDate = datetime.now(pytz.timezone('Asia/Kolkata')), endDate = datetime.now(pytz.timezone('Asia/Kolkata')), 
            exchange = None, token = None, symbol = None, orderId = None, brokerAccountId = None, status = 'COMPLETE'
            ):
        
        qFilter = Q(user = self.User, tradeDate__range = (startDate, endDate), status = status)

        if exchange:
            qFilter&= Q(exchange = exchange)
        
        if orderId:
            qFilter&= Q(orderId = orderId)
        
        if brokerAccountId:
            qFilter&= Q(target_id = brokerAccountId)

        if token:
            qFilter&= Q(token = token)

        if symbol:
            qFilter&= Q(symbol = symbol)
        
        logs = JobbingLog.objects.filter(qFilter).order_by('updatedOn')
        return logs

    def createOrderLog(self, userid, orderId, brokerAccountId, verboseOrder, status = ''):

        log = JobbingLog.objects.filter(user_id = userid, target_id = brokerAccountId, orderId = orderId).first()
        if log:
            # log = Strategy1Log.objects.select_for_update().get(id=log.id)
            log.tradeDate   = datetime.now(pytz.timezone('Asia/Kolkata')) 
            log.quantity    = verboseOrder['quantity']
            log.price       = verboseOrder['price']
            if status != '':
                log.status      = status
            log.save()
            
        else:
            if status == '':
                status = 'OPEN'
            log = JobbingLog(
                user_id         = userid,
                target_id       = brokerAccountId,  
                exchange        = Exchanges.objects.get(code=verboseOrder['exchSeg']),
                token           = verboseOrder['token'],
                symbol          = verboseOrder.get('symbol',''),
                orderId         = orderId,
                tradeDate       = datetime.now(pytz.timezone('Asia/Kolkata')),
                quantity        = verboseOrder['quantity'],
                price           = verboseOrder['price'],
                orderType       = verboseOrder['tranType'],
                intraday        = True if verboseOrder['variety'] == 'NORMAL' else False,
                currStock       = 0,
                status          = status,
                orderCategory   = verboseOrder['orderCategory']
            )
            log.save()

        return log  


    def  executeOrderPair(self,
        userid, target, exchange, token, numberOfOrders, 
        basePrice,  lotSizeBuy,    tickSizeBuy,   
        buyOnly=False, sellOnly = False, simulation=False, tickSizeSell = 0, lotSizeSell = 0, 
        flagReverseTick = False, createLog = True,
        orderCatagory = 'Normal', gttBuyBuffer = 0, gttSellBuffer = 0, wait=0, count = 1
        ):

        broker = Broker(target.broker.brokerId)
        if broker.canPlaceOrder(exchange,1,1):
            workerOrderPair(self.code,
                userid, target.id, exchange, token, numberOfOrders, 
                basePrice,  lotSizeBuy,    tickSizeBuy,  buyOnly, sellOnly, 
                simulation, tickSizeSell, lotSizeSell, 
                flagReverseTick, createLog,
                orderCatagory, gttBuyBuffer, gttSellBuffer, wait, count
            )
        else:
            t1 = Thread(target=workerOrderPair, args=(self.code,
                userid, target.id, exchange, token, numberOfOrders, 
                basePrice,  lotSizeBuy,    tickSizeBuy,  buyOnly, sellOnly, 
                simulation, tickSizeSell, lotSizeSell, 
                flagReverseTick, createLog,
                orderCatagory, gttBuyBuffer, gttSellBuffer, wait, count
            ))
            t1.start()


        # workerOrderPair(self.code,
        #     userid, target.id, exchange, token, numberOfOrders, 
        #     basePrice,  lotSizeBuy,    tickSizeBuy,  buyOnly, sellOnly, 
        #     simulation, tickSizeSell, lotSizeSell, 
        #     flagReverseTick, createLog,
        #     orderCatagory, gttBuyBuffer, gttSellBuffer, wait, count
        # )        

    def updateLogStatusFromOrderBook(self, brokerObj, orderCatagory, targetId, exchange, publish=False):
    # checking actual status of the order - in case of rejection or cancelled after order is placed
        try:
            defStatus = False
            checkLog = JobbingLog.objects.filter(
                            user_id     = self.User.id, 
                            target_id   = targetId, 
                            exchange__code    = exchange,
                            orderCategory = orderCatagory,
                            status          = 'OPEN'
                            )    
            if not checkLog:
                return True
            
            lstOrder = brokerObj.readOrderBook(OrderCatagory=orderCatagory)
            for log in checkLog:
                for ord in lstOrder:
                    if ord['orderId'] == log.orderId and ord.get('status') != log.status and not isBlankOrNone(ord.get('status')):
                        if ord['status'] in ['REJECTED','CANCELED','COMPLETE']:
                            log.status = ord.get('status')
                            log.save()
                            logger.debug(f"order status for orderid {log.orderId} updated to {ord.get('status')}")
                            return True
                        if publish:
                            identifier = {
                                'MTYPE': 'ORD',
                                'QID': brokerObj.OrderQ,
                                MSGATTRIB.ACCOUNTID: brokerObj.Account.id
                            }
                            lord = {
                                't': 'om', 'norenordno': ord.get('orderId'), 
                                'uid': brokerObj.Account.clientId, 'actid': str(brokerObj.Account.clientId), 'exch': ord.get('exchange'), 
                                'tsym': ord.get('symbol'), 'trantype': ord.get('tranType')[0:1], 'qty': str(ord.get('quantity')), 'prc': ord.get('averagePrice'), 'pcode': 'M', 'remarks': '', 
                                'rejreason': ' ', 'status': 'PENDING', 'reporttype': 'ModAck', 'prctyp': 'LMT', 'ret': 'DAY', 
                                'exchordid': ord.get('orderId'), 'dscqty': '0', 'exch_tm': ord.get('OrderedTime')
                                }
                            lord.update(identifier)     
                            
                            brokerObj.pubsub.publish(brokerObj.OrderQ, lord)  
                            defStatus = True                      
        except Exception as e:
            logger.error(f'failed to update missing order message sync {str(e)}')
            defStatus = False
        finally:
            return defStatus

    def resyncStrategyValues(self, brokerAccount, exchange=None):
        self.getActiveSetup(exchange)

        for accountId in self.ActiveAccounts:            
            brokerObj = brokerAccount.getBrokerObject(accountId)
            holdings = brokerObj.getHoldings()
            positions = brokerObj.getPositions()
            tradeBook = brokerObj.readTradeBook()
            setups = self.Setups.filter(target_id = accountId)
            for holding in holdings:
                tsyms = holding.get('exch_tsym')
                for tsym in tsyms:
                    setup = setups.filter(exchange = tsym.get('exch'), token = tsym.get('token')).first()
                    if setup:
                        setup.stockCurrent = int(tsym.get('pp'))
                        for trade in tradeBook:
                            if trade.get('exchange') == tsym.get('exch') and trade.get('token') == tsym.get('token'):
                                setup.priceCurrent = Decimal(trade.get('fillprice'))
                                setup.save()
                                break

            for position in positions:
                setup = setups.filter(exchange = position.get('exch'), token = position.get('token')).first()
                if setup:
                    setup.stockCurrent = int(position.get('netqty'))
                    for trade in tradeBook:
                        if trade.get('exchange') == position.get('exch') and trade.get('token') == position.get('token'):
                            setup.priceCurrent = Decimal(trade.get('fillprice'))
                            setup.save()
                            break


        # for script in self.ActiveScripts:
        #     activeScript = {
        #         'OrderQId'      : broker.getQueueId(self.User.username,setup.target.clientId,setup.exchange,'O') if self.requireOrderCallback else None,
        #         'TickQId'       : broker.getQueueId(self.User.username,setup.target.clientId,setup.exchange,'T') if self.requireTickCallback else None,
        #         # 'strategyCode'  : self.code,
        #         'accountId'     : setup.target.id,
        #         'clientId'      : setup.target.clientId,
        #         'brokerId'      : setup.target.broker.brokerId,
        #         'exchange'      : setup.exchange,
        #         'token'         : setup.token,
        #         'symbol'        : setup.symbol
        #     }        

# Class class Strategy1(Strategy): Ended here ********************************

# @transaction.atomic

@shared_task(bind=True)
def workerS1OrderCallback(self, strategyCode, accId, exchange, cancelOld = True):
    accountId = int(accId)
    ba = BrokerAccounts.objects.filter(id = accountId).first()
    if not ba:
        return None
    telegram = Telegram(ba.user.id)
    # telegram.sendMessage(f'Order processing for {exchange} started')
    strategy = Strategy.getStrategyInstance(ba.user,strategyCode, exchange)
    brokerAccount = BrokerAccount(ba.user,accountId)
    brokerAccount.Connect(accountId,True)
    connObj = brokerAccount.getBrokerObject(accountId)
    if connObj is None:
        telegram.sendMessage(f'Error while connecting broker account')
        logger.error(f'Error while connecting broker account for user {ba.user.username}')
    
    setup = strategy.Setups.filter(target_id = accountId).first()
    broker = Broker(brokerAccount.BrokerAccounts[0].broker.brokerId)
    pubsub = PubSub()
    broker_inst = broker.getBrokerInstance(brokerAccount.BrokerAccounts[0].broker.brokerId, brokerAccount.BrokerAccounts[0].id)
    if broker_inst:
        pubsub.subscribe(broker_inst.OrderQ)
    else:
        logger.error(f'could not get broker instance for {brokerAccount.BrokerAccounts[0].nickName}')
        return False
    # if cancelOld:
    #     logger.debug('starting cancel order')
    #     connObj.cancelOrders([], exchange)
    #     logger.debug('end of cancel order')
    
    while broker.isMarketOpen(exchange):    
        # pubsub.setLastAccess(OrderQId)
        
        ord = pubsub.get_message()
        # ord = {'id': '1', 'exchange': 'MCX','price': '12.34'}
        if ord == None:
            sleep(0.5)
            # updStatus = strategy.updateLogStatusFromOrderBook(connObj, 'Normal', accId, exchange, publish=True)            
            # if not updStatus:
            #     sleep(2)
            #     pass
            # else:
            #     pass
            #     sleep(2)
            continue
        try:
            print(f"Jobbing callback for order {ord}")
            # print(f'Read data {ord} for QID {OrderQId}')
            logger.warning(ord)
            if ord.get('type', '') == 'TERMINATE':
                if ord.get('strategy', strategy.code) == strategy.code and ord.get('exchange', exchange) == exchange and ord.get('accountId', accId) == accId:
                    logger.debug(f'Termianted {strategy.code}:{exchange}:Acc{accId}')
                    pubsub.clear_message()
                    break

                                             

            if ord.get('MTYPE') == 'ORD':
                ord = broker_inst.formatOrderCallback(ord)
                if ord.get('exchSeg') != exchange:
                    logger.error(f"other exchange: ord:{ord.get('exchSeg')}: {exchange}")
                    continue

            if isBlankOrNone(ord.get('orderId')):
                logger.error(f'invalid order data {ord}')
                continue

            buyOnly = False
            sellOnly = False

            logTrade = False
            flagReverseTick = False
            if ord['status'] == 'COMPLETE':
                logTrade = True
            else:
                continue
                #     currLog = JobbingLog.objects.filter( target_id = accountId, orderId = ord['orderId']).first()
            #     if currLog:
            #         # currLog = Strategy1Log.objects.select_for_update().get(id=currLog.id)
            #         if currLog.status != ord.get('status') and not isBlankOrNone(ord.get('status')):
            #             currLog.status = ord['status']
            #             currLog.updatedOn   = datetime.now(pytz.timezone('Asia/Kolkata'))
            #             currLog.save()
            #             logger.info(f"Order log status updated {ord.get('orderId')} {currLog.status}")
            #     continue
            setup = strategy.Setups.filter(exchange__code=ord['exchSeg'], token=ord['token'], target_id=accountId).first()
            if setup:
                currStock = setup.stockCurrent
            else:
                currStock = 0
                logger.error(f"No setup found for {ord['exchSeg']} : {ord['token']}")
                telegram.sendMessage(f"No setup found for {ord['exchSeg']} : {ord['token']}")
                continue

            # logStock = JobbingLog.objects.filter(user = strategy.User, exchange__code = ord['exchSeg'], token = ord['token'], status = 'COMPLETE').order_by('-updatedOn').first()
            # if logStock:
            #     currStock = logStock.currStock
            # else:
            #     currStock = setup.stockCurrent

            currLog = JobbingLog.objects.filter(target_id=accountId, orderId=ord['orderId']).first()
            if currLog:

                if currLog.status in ['COMPLETE']:
                    continue

                if strategy.isActive == False:  # broker.canPlaceOrder(exchange.code) and
                    continue

                lotSizeBuy = setup.buyLot
                lotSizeSell = setup.sellLot
                basePrice = Decimal(ord['limitPrice'])
                if ord['tranType'] == 'BUY':

                    currStock += currLog.quantity
                    setup.stockCurrent = currStock

                else:
                    flagReverseTick = True

                    currStock -= currLog.quantity
                    setup.stockCurrent = currStock

                currLog.status = ord.get('status')
                # currLog.price       = ltp
                currLog.currStock = currStock
                currLog.updatedOn = datetime.now(pytz.timezone('Asia/Kolkata'))
                currLog.save()
                logger.debug(f'after saving in db {currLog.status} {currLog.orderId} Qty:{currStock}')
                setup.priceCurrent = basePrice
                setup.save()
                message = f"User:{ba.user}, {ord['tranType']}-{setup.exchange.code}:{ord['symbol']} - Qty ( {currLog.quantity} @ {basePrice} )"
                telegram.sendMessage(message)
                logger.info(message)
                # strategy.Telegram.sendMessage(message)

                # if waitForMarketOpen(0, setup.exchange) == False:
                #     print(f'Market {setup.exchange} closed, terminating worker')
                #     # strategy.ConnectionObject.closeWebSocket(ws)
                #     strategy.setStatus('TERMINATE')
                #     return

                if logTrade and setup:
                    if setup.stockCurrent >= setup.stockMax:
                        sellOnly = True
                    if setup.stockCurrent <= setup.stockMin:
                        buyOnly = True
                    # telegram.sendMessage('Trying to place subsequent order')
                    logger.debug(f'work order pair initiating for {setup.exchange.code}:{setup.token} {basePrice}')
                    if broker.canPlaceOrder(exchange):

                        workerOrderPair(strategy.code, strategy.User.id, setup.target.id, setup.exchange.code, setup.token, 1,
                                        basePrice, lotSizeBuy, setup.buyTick,
                                        buyOnly, sellOnly, setup.simulate, setup.sellTick, setup.sellLot, flagReverseTick)
                    else:
                        t1 = Thread(target=workerOrderPair,
                                    args=(
                                        strategy.code, strategy.User.id, setup.target.id, setup.exchange.code, setup.token, 1,
                                        basePrice, lotSizeBuy, setup.buyTick,
                                        buyOnly, sellOnly, setup.simulate, setup.sellTick, setup.sellLot, flagReverseTick
                                    )
                                    )
                        t1.start()

                    logger.debug(f'work order pair completed for {setup.exchange.code}:{setup.token} {basePrice}')
                    # sleep(1)
                    # workerOrderPair.delay(strategy.code, strategy.User.id, setup.target.id, setup.exchange, setup.token, 1,
                    #                 basePrice, lotSizeBuy,setup.buyTick,
                    #                 buyOnly, sellOnly, setup.simulate, setup.sellTick, setup.sellLot, flagReverseTick)


        except Exception as exc:
            traceback.print_exc()
            # pubsub.unsubscribe(OrderQId)
            logger.error(exc)                
            # telegram.sendMessage('Error processing cycle order update callback')

    telegram.sendMessage(f'Process for Exchange {exchange} is completed')
    sendTradesbyEmail.delay(strategy.User.id,exchange)
    
    telegram.sendMessage(f'Email with trade list for Exchange {exchange} is sent')

@shared_task(bind=True)
def sendTradesbyEmail(self, userid, exchange, logDate=''):
    qFilter = Q(user_id = userid, exchange__code = exchange)
    
    if logDate == '':
        objLogDate = datetime.now() 
    else: 
        objLogDate = datetime.strptime(logDate , "%Y%m%d")

    qFilter &= Q(tradeDate__date = objLogDate.date())    
    logs = JobbingLog.objects.filter(qFilter).order_by('exchange','token','tradeDate')    
    user = User.objects.filter(id=userid).first()
    social = UserSocialProfile.objects.filter(user = user).first()
    if logs:
        excelfile = BytesIO()
        wb = xlwt.Workbook(encoding='utf-8')
        ws = wb.add_sheet('TradeLog')
        # Column Header of Excel FIle
        ws.write(0, 0, 'Trade Date')
        ws.write(0, 1, 'Exch/Seg')
        ws.write(0, 2, 'Token')
        # ws.write(0, 3, 'Symbol')
        ws.write(0, 3, 'Name')
        ws.write(0, 4, 'Order Id')
        ws.write(0, 5, 'Trade Type')        
        ws.write(0, 6, 'Qty')
        ws.write(0, 7, 'Price')                
        ws.write(0, 8, 'Status')
        ws.write(0, 9, 'Executed on')
        currRow = 1
        for log in logs:            
            
            # write cell of the excel sheet            
            ws.write(currRow, 0, convertUTCtoIST(log.tradeDate).strftime("%d-%m-%Y %H:%M:%S"))
            ws.write(currRow, 1, log.exchange.code)
            ws.write(currRow, 2, log.token)
            ws.write(currRow, 3, log.symbol)
            # ws.write(currRow, 4, script.name)
            ws.write(currRow, 4, log.orderId)
            ws.write(currRow, 5, log.orderType)        
            ws.write(currRow, 6, log.quantity)
            ws.write(currRow, 7, log.price)                
            ws.write(currRow, 8, log.status)
            ws.write(currRow, 9, '' if log.updatedOn == None else convertUTCtoIST(log.updatedOn).strftime("%d-%m-%Y %H:%M:%S"))
            currRow += 1

        # save excel file and start attaching to email
        wb.save(excelfile)
        email = EMail()
        subject = 'Dhananjay: Trade Log ' + objLogDate.strftime('%d/%m/%Y')
        body =  f'''
                Dear  {user.first_name},
                Enclosed the trade log for the subject date. 
                Trade log is for reference and do not claim to be absolutely true.
                In case you find any issue please reply to this mail.

                Thanks, 
                Team Dhananjay'
                '''
        emailto = [social.email]

        email.send(subject,body,emailto, excelfile, f"tradeLog{objLogDate.strftime('%d%m%Y')}.xls", 'application/ms-excel')


def thread1TickCallback():
    # use this method in case to act of price change 
    pass

def getOrder(lstOrder:list,orderId:str):
    for ord in lstOrder:
        if ord.get('orderId') == orderId:
            return ord

    return None 

def get_redis_lock_key(userid, targetId, strategyCode, token, exchange, tranType, price):
    hash_input = f"{userid}:{targetId}:{strategyCode}:{token}:{exchange}:{tranType}:{price}"
    return f"lock:orderpair:{hashlib.md5(hash_input.encode()).hexdigest()}"

@shared_task(bind=True)
def  workerOrderPair(self,
        strategyCode, userid, targetId, exchange, token, numberOfOrders, 
        basePrice,  lotSizeBuy,    tickSizeBuy,   
        buyOnly=False, sellOnly = False, simulation=False, tickSizeSell = 0, lotSizeSell = 0, 
        flagReverseTick = False, createLog = True,
        orderCatagory = 'Normal', gttBuyBuffer = 0, gttSellBuffer = 0, wait=0, count = 1 
    ):
    # telegram = Telegram(userid)
    user = User.objects.filter(id = userid).first()
    strategy = Strategy.getStrategyInstance(user,strategyCode,exchange)
    brokerAccount = BrokerAccount(user, targetId)
    brokerAccount.Connect(targetId, True)
    logger.debug(f'Broker Account connected for {user.username}')
    redis = getRedisInstance()
    # OrderCatagory = 'All', 'GTT','Normal'
    broker = Broker(brokerAccount.BrokerAccounts[0].broker.brokerId)
    if broker.canPlaceOrder(exchange, wait, count) == False:    
        logger.warning(f'Order place timed out {user.username}:{exchange}:{token}')
        return []
        
    # conn = Connection.get('Connection')
    brokerObj = brokerAccount.getBrokerObject(targetId)

    lstOrd = []    
    if tickSizeSell == 0:
        tickSizeSell = tickSizeBuy

    if lotSizeSell == 0:
        lotSizeSell = lotSizeBuy


    orderId = ''
    # Check for any Open Orders
    checkLog = JobbingLog.objects.filter(
                    user_id     = userid, 
                    target_id   = targetId, 
                    exchange__code    = exchange,
                    token       = token,
                    orderCategory = orderCatagory,
                    status          = 'OPEN'
                    )
    # checking actual status of the order - in case of rejection or cancelled after order is placed
    lstOrder = brokerObj.readOrderBook(OrderCatagory=orderCatagory)
    for log in checkLog:
        for ord in lstOrder:
            if ord['orderId'] == log.orderId and ord.get('status') != log.status and not isBlankOrNone(ord.get('status')):
                log.status = ord.get('status')
                log.save()
                logger.debug(f"order status for orderid {log.orderId} updated to {ord.get('status')}")

    checkLog = JobbingLog.objects.filter(
                    user_id     = userid, 
                    target_id   = targetId, 
                    exchange__code    = exchange,
                    token       = token,
                    orderCategory = orderCatagory,
                    status          = 'OPEN'
                    ).order_by('-tradeDate','-updatedOn')
        
    buyLog = checkLog.filter(orderType   = 'BUY').first()
    sellLog = checkLog.filter(orderType   = 'SELL').first()

    
    if flagReverseTick:
        buyPrice = round(float(basePrice) - ( float(tickSizeSell)  ), 2)
        sellPrice = round(float(basePrice) + ( float(tickSizeBuy)  ), 2)
    else:
        buyPrice = round(float(basePrice) - ( float(tickSizeBuy) ) , 2)
        sellPrice = round(float(basePrice) + ( float(tickSizeSell) ) , 2)

    if sellOnly == False:
       
        log = buyLog
        if log:
            lstOrder = brokerObj.readOrderBook(log.orderId, orderCatagory)
        
            order = lstOrder[0]
        # order = getOrder(lstOrder,log.orderId)
            if order:
                if order.get('status') in ['OPEN']:
                    action = 'Update'                    
                    orderId = log.orderId
                else:
                    action = 'Create'
                    orderId = 0
            else:
                logger.error(f'order not found in order book {log.orderId} token {token}')
        else:
            action = 'Create'
            orderId = 0    

        # orderparams = prepareParams(
        #     action, token, exchange, 'BUY',buyPrice, lotSize, False, orderId)        
        logger.debug(f'order paid: buy order with action {action}')
        # brokerObj

        # lstVerboseOrder = brokerObj.VerboseOrder(
        #     'NORMAL', exchange, token, '', 'BUY', 'LIMIT', 'DELIVERY', buyPrice, lotSizeBuy, 0, 'DAY', 0, 0, 0, orderId, orderCatagory, gttBuyBuffer, gttSellBuffer)
        # if type(lstVerboseOrder) != list:
        #     lstVerboseOrder = [lstVerboseOrder]
        lock_key = get_redis_lock_key(userid, targetId,strategyCode, token, exchange, 'BUY', buyPrice)
        # Try acquiring lock
        if redis.set(lock_key, "1", nx=True, ex=settings.REDIS_LOCK_EXPIRY):  # Lock expires in 5 seconds
            Order = brokerAccount.submitOrder(action, targetId, 'NORMAL', exchange, token, '', 
                                        'BUY', 'LIMIT', 'DELIVERY', buyPrice, lotSizeBuy, 0, 'DAY', 0, 0, 0,orderId, simulation, wait=wait, count =count)

            if not isBlankOrNone(Order['orderId']):                
                orderId = Order.get('orderId','')
                lstOrderBook = brokerAccount.readOrderBook(targetId,orderId, orderCatagory)      
                if len(lstOrderBook) > 0:
                    logger.debug(f'order created with id {orderId}')
                    # strategy.createOrderLog(strategy.User.id, orderId, target.id, Order, status = lstOrderBook[0].get('status',''))
                    log =strategy.createOrderLog(strategy.User.id, orderId, targetId, Order, status = 'OPEN')
                    logger.debug(f'order updated in log for id {orderId} action {action}')
                    # if log:
                    #     telegram.sendMessage(f'{log.orderType} {log.exchange}:{log.symbol}-{log.quantity}@{log.price}')
                lstOrd.append(Order) 
        else:
            logger.warning(f"Skipping duplicate workerOrderPair task for {token}")

    if buyOnly == False:
        

        log = sellLog               
        if log:
            lstOrder = brokerAccount.readOrderBook(targetId, log.orderId, OrderType = 'All')
            ord = lstOrder[0]
            if ord:
                # ord = getOrder(lstOrder,log.orderId)
                if ord.get('status') in ['OPEN']:                
                    action = 'Update'
                    
                    orderId = log.orderId
                else:
                    action = 'Create'
                    orderId = 0
            else:
                logger.error(f'order not found in order book {log.orderId} token {token}')
        else:
            action = 'Create'
            orderId = 0            

        lock_key = get_redis_lock_key(userid, targetId, strategyCode, token, exchange, 'SELL', sellPrice)
        # Try acquiring lock
        if redis.set(lock_key, "1", nx=True, ex=settings.REDIS_LOCK_EXPIRY):  # Lock expires in 5 seconds
            logger.debug(f'sell order processing started with action {action}')
            Order = brokerAccount.submitOrder(action, targetId, 'NORMAL', exchange, token, '', 
                                        'SELL', 'LIMIT', 'DELIVERY', sellPrice, lotSizeSell, 0, 'DAY', 0, 0, 0,orderId, simulation,wait = wait, count = count)
            

            if not isBlankOrNone(Order['orderId']):                
                orderId = Order.get('orderId','')
                # if lstOrder[0]['orderStatus'] == ['OPEN','PENDING','COMPLETE']:
                lstOrderBook = brokerAccount.readOrderBook(targetId,orderId, orderCatagory)      
                if len(lstOrderBook) > 0:
                    logger.debug(f'order created with id {orderId}')
                    # strategy.createOrderLog(strategy.User.id, orderId, target.id, Order, status = lstOrderBook[0].get('status',''))
                    log = strategy.createOrderLog(strategy.User.id, orderId, targetId, Order, status = 'OPEN')
                    logger.debug(f'order updated in log for id {orderId} action {action}')
                    # if log:
                    #     telegram.sendMessage(f'{log.orderType} {log.exchange}:{log.symbol}-{log.quantity}@{log.price}')
                lstOrd.append(Order)  

    # return lstOrd

