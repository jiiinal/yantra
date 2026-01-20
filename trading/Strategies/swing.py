import hashlib
import logging
import math
import traceback
# from mainapp.views.utils import pdSeries
from datetime import datetime
from decimal import Decimal
# from mainapp.views.logger import logging
# for sending Email
from io import BytesIO
from threading import Thread
from time import sleep

import pytz
import xlwt
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q

# from trading.views.Strategies.strategy import getStrategyQueueId
from social.models import UserSocialProfile
from social.views.email import EMail
from social.views.telegram import Telegram
from trading.Entities.BrokerAccounts.brokerAccount import BrokerAccount
from trading.Entities.Brokers.bnrathi import MSGATTRIB
from trading.Entities.Brokers.broker import Broker
# from trading.views.Redis.messageQueue import MessageQueue
# from trading.views.Redis.rabbitMQ import RabbitMQ
from trading.Redis.pubsub import PubSub
from trading.Redis.pubsub import getRedisInstance
# from trading.views.Entities.brokerAccount import BrokerAccount
from trading.Strategies.strategy import Strategy
from trading.models import BrokerAccounts, Exchanges
from trading.models import SwingSettings, StrategyStatus, Strategis, SwingLog
from utils.views import isBlankOrNone, convertUTCtoIST

logger = logging.getLogger(__name__)

STRATEGY_CODE = 'SWING'


class Swing(Strategy):
    """
    Implements the Swing strategy for automated order placement and management.
    Handles setup, order scheduling, callbacks, and log updates for each user/account.
    """

    def __init__(self, user, exchange=None) -> None:
        """
        Initialize the Swing strategy for a user and exchange.
        Loads strategy settings, active setups, and prepares pubsub for order callbacks.
        """
        self.code = STRATEGY_CODE
        self.exchange = exchange
        StrategyMaster = Strategis.objects.filter(code=self.code).first()
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
        """
        Loads all active Swing setups for the user and exchange.
        Returns the queryset of active setups and updates internal lists.
        """
        lstActiveAccounts = []
        lstActiveScripts = []
        self.Setups = SwingSettings.objects.select_related("target").filter(user=self.User, isActive=True, target__isActive=True).order_by('target_id', 'exchange')
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

    def isActive(self, user=None):
        """
        Checks if the strategy is active for the user.
        Returns True if active setups exist, False otherwise.
        """
        if not self.StrategyMaster.isActive:  # check in the master table
            return False

        if not user:
            user = self.User

        if user == None:
            self.telegram.sendMessage(f'No user defined for strategy code {self.code}')
            raise Exception(f'No user defined for strategy code {self.code}')

        setups = self.getActiveSetup()
        return setups != None

    def getScriptForTickCallback(self):
        """
        Returns a list of scripts for tick callback subscription (currently not implemented).
        """
        # it should be in the format of {'accountId': {accountId}, 'exchange': {exchange}, 'token': {token}, 'symbol':{symbol}}
        return []

    def getOrders(self, status='OPEN'):
        """
        Returns all SwingLog orders for the given status.
        """
        return SwingLog.objects.filter(status=status)

    @property
    def requireOrderCallback(self):
        """
        Indicates if order callback workers are required (always True).
        """
        return True

    @property
    def requireTickCallback(self):
        """
        Indicates if tick callback workers are required (currently False).
        """
        return False

    def getStatus(self):
        """
        Returns the current status of the strategy for the user.
        """
        status = StrategyStatus.objects.filter(user=self.User, strategy=self.StrategyMaster).first()
        if status:
            return status.currStatus
        else:
            return None

    def setStatus(self, status):
        """
        Sets the current status of the strategy for the user.
        """
        stat = StrategyStatus.objects.filter(user=self.User, strategy=self.StrategyMaster).first()
        if stat:
            stat.currStatus = status
        else:
            stat = StrategyStatus(
                user=self.User,
                strategy=self.StrategyMaster,
                currStatus=status,
                taskId=''
            )
        stat.save()

    def initiate(self, exchange=None):
        """
        Initiates the strategy, sets status, and sends notification.
        Returns True if active, False otherwise.
        """
        try:
            # print("Yesss in swings")
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

    def start(self, brokerAccount, exchange=None, initialStrategy=True):
        """
        Starts the strategy execution: order callback, tick callback, and initial order placement.
        """
        self.telegram.sendMessage(f'{self.code} : execution started')

        self.processOrderCallback(exchange)
        self.telegram.sendMessage(f'{self.code} : Order tracking started')
        #
        self.processTickCallback(exchange)
        self.telegram.sendMessage(f'{self.code} : price tracking Started if applicable')
        sleep(2)
        if initialStrategy:
            self.createInitialOrder(brokerAccount)
        self.telegram.sendMessage(f'{self.code} : Initial Order Placed')

    def createInitialOrder(self, brokerAccount):
        """
        Cancels old orders and creates initial order pairs for each active setup/account.
        This is the entry point for the Swing strategy.
        """
        lstAccIds = []
        brokerObj = None

        for setup in self.Setups:
            if not setup.target.id in lstAccIds:
                lstAccIds.append(setup.target.id)

        # Cancel all existing open orders
        for accId in lstAccIds:
            brokerObj = brokerAccount.getBrokerObject(accId)
            orders = self.getOrders('OPEN')
            if orders:
                lstOrd = [ord.orderId for ord in orders]
                brokerObj.cancelOrders(lstOrd)
                sleep(1)

        for setup in self.Setups:
            simulation = setup.simulate
            lotSize = setup.lot
            lotSizeStopLoss = setup.slLot if setup.useSlLot else setup.lot
            gap = setup.gap
            stopLoss = setup.stopLoss

            # Remove all older unexecuted orders from log
            SwingLog.objects.filter(
                user=self.User,
                exchange=setup.exchange,
                token=setup.token
            ).exclude(status='COMPLETE').delete()

            # Get last completed order to determine base price
            log = SwingLog.objects.filter(
                user=self.User,
                exchange=setup.exchange,
                token=setup.token,
                status__in=['COMPLETE', 'PARTIAL']
            ).order_by('-updatedOn').first()

            # Determine initial base price
            if log:
                if setup.priceCurrent > 0:
                    basePrice = setup.priceCurrent
                    self.telegram.sendMessage(f'{self.code} : Override Price {basePrice}')
                else:
                    basePrice = log.price
                    self.telegram.sendMessage(f'{self.code} : Base Price {basePrice} as per last Transaction')
            else:
                basePrice = setup.priceCurrent
                self.telegram.sendMessage(f'{self.code} : no prev record, setup base price {basePrice}')

            if self.getStatus() == 'TERMINATE':
                return

            brokerConnection = brokerObj.getConnectionObject()
            # Check if catchup orders are needed and get adjusted base price
            catchup_placed, adjusted_base_price, cmp = self.checkAndPlaceCatchupOrders(
                brokerConnection,
                setup,
                basePrice
            )
            logger.info("catchup_placed, adjusted_base_price, cmp : {}, {}, {}".format(
                catchup_placed,
                adjusted_base_price,
                cmp
            ))
            if catchup_placed:
                # Use the adjusted base price aligned to grid
                basePrice = cmp
                setup.priceCurrent = basePrice
                setup.save()
                logger.info(
                    f'{self.code} : Base price adjusted. catchup_placed, adjusted_base_price, cmp : {catchup_placed}, {adjusted_base_price}, {cmp}'
                )

            # Determine order restrictions based on position
            buyOnly = False
            sellOnly = False

            if setup.stockCurrent >= setup.stockMax:
                sellOnly = True
            if setup.stockCurrent <= setup.stockMin:
                buyOnly = True

            try:
                # Place the normal order pair at the (possibly adjusted) basePrice
                self.executeOrderPairSwing(
                    self.User.id, setup.target, setup.exchange.code, setup.token, setup.dayOrders,
                    basePrice, lotSize, gap, buyOnly, sellOnly, simulation, stopLoss, lotSizeStopLoss,
                    True, setup.orderCatagory, wait=setup.wait, count=setup.count
                )

            except Exception as exc:
                print(exc)
                traceback.print_exc()
                continue

    def processOrderCallback(self, exchange=None):
        """
        Starts order callback workers for each active account/exchange.
        Subscribes to broker order queues for status updates.
        """
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
                    'accountId': script.get('accountId'),
                    'exchange': script.get('exchange'),
                    # 'OrderQId'      : script.get('OrderQId')
                }

                if not dict in lstUnique:
                    lstUnique.append(dict)

            lstThreads = []
            for item in lstUnique:
                # t1 = Thread(target=workerSwingOrderCallback, args=(self.code, str(item.get('accountId')), item.get('exchange').code)
                #             )
                # lstThreads.append(t1)
                workerSwingOrderCallback.delay(self.code, str(item.get('accountId')), item.get('exchange').code)
                # workerSwingOrderCallback(self.code, str(item.get('accountId')), item.get('exchange'), item.get('OrderQId'))
            for t1 in lstThreads:
                t1.start()
        # sleep(5)
        return True

    def processTickCallback(self, exchange=None):
        """
        Stub for tick callback worker (not implemented).
        """
        if self.requireTickCallback:
            pass

        return True

    def getOrderLog(self, startDate=datetime.now(pytz.timezone('Asia/Kolkata')), endDate=datetime.now(pytz.timezone('Asia/Kolkata')),
                    exchange=None, token=None, symbol=None, orderId=None, brokerAccountId=None, status='COMPLETE'):
        """
        Returns SwingLog entries for the given filters (date, exchange, token, etc.).
        """

        qFilter = Q(user=self.User, tradeDate__range=(startDate, endDate), status=status)

        if exchange:
            qFilter &= Q(exchange=exchange)

        if orderId:
            qFilter &= Q(orderId=orderId)

        if brokerAccountId:
            qFilter &= Q(target_id=brokerAccountId)

        if token:
            qFilter &= Q(token=token)

        if symbol:
            qFilter &= Q(symbol=symbol)

        logs = SwingLog.objects.filter(qFilter).order_by('updatedOn')
        return logs

    def checkAndPlaceCatchupOrders(self, brokerConnection, setup, basePrice):
        """
        Checks if market opened at a significantly different price and places catchup orders.

        Args:
            brokerConnection: Broker connection object
            setup: Setup configuration object
            basePrice: Previous base price from log

        Returns:
            Tuple of (should_place_catchup, adjusted_base_price, cmp)
            - should_place_catchup: Boolean indicating if catchup was needed
            - adjusted_base_price: New base price aligned to grid (or original if no catchup)
            - cmp: Current market price (or None if fetch failed)
        """
        try:
            response = brokerConnection.get_quotes(exchange=setup.exchange.code, token=setup.token)

            if not response or response.get('stat') != 'Ok':
                print(f"Could not fetch CMP for {setup.exchange.code}:{setup.token}")
                return (False, basePrice, basePrice)

            cmp = float(response.get('lp', 0))

            if cmp <= 0:
                print(f"Invalid CMP ({cmp}) for {setup.exchange.code}:{setup.token}")
                return (False, basePrice, basePrice)

            # Determine grid interval (always the larger value for grid structure)
            original_gap = max(float(setup.gap), float(setup.stopLoss))

            # Calculate price difference
            price_diff = cmp - float(basePrice)

            # Check if catchup is needed
            if abs(price_diff) <= original_gap:
                # Price is within one grid level - no catchup needed
                print(f"CMP ({cmp}) close to base ({basePrice}), no catchup needed")
                return (False, basePrice, cmp)

            # Calculate missed levels
            if price_diff > 0:
                # Price opened HIGH - missed BUYs
                steps_to_current = math.ceil(price_diff / original_gap)
                missed_levels = abs(steps_to_current - 1) if steps_to_current > 1 else 0

                if missed_levels > 0:
                    logger.info(
                        f'{self.code} : 📈 Price JUMPED UP!\n'
                        f'Base: {basePrice} → CMP: {cmp}\n'
                        f'Missed {missed_levels} BUY levels: '
                        f'{[float(basePrice) + (i * original_gap) for i in range(1, missed_levels + 1)]}'
                    )

                    if missed_levels > abs(setup.stockMin):
                        logger.info(f"stockMin was {setup.stockMin}, hence updating missed levels")
                        missed_levels = abs(setup.stockMin)

                    # Place catchup BUY order
                    self.createCatchupOrder(setup, missed_levels, 'BUY', cmp)

                    # Calculate new base price aligned to grid
                    new_base_price = float(basePrice) + (steps_to_current * original_gap)
                    return (True, new_base_price, cmp)

            else:
                # Price opened LOW - missed SELLs
                steps_to_current = math.floor(price_diff / original_gap)
                missed_levels = abs(steps_to_current + 1) if steps_to_current < -1 else 0

                if missed_levels > 0:
                    logger.info(
                        f'{self.code} : 📉 Price DROPPED DOWN!\n'
                        f'Base: {basePrice} → CMP: {cmp}\n'
                        f'Missed {missed_levels} SELL levels: '
                        f'{[float(basePrice) - (i * original_gap) for i in range(1, missed_levels + 1)]}'
                    )

                    if missed_levels > setup.stockMax:
                        logger.info(f"stockMax was {setup.stockMax}, hence updating missed levels")
                        missed_levels = setup.stockMax

                    # Place catchup SELL order with multiple lots
                    self.createCatchupOrder(setup, missed_levels, 'SELL', cmp)

                    # Calculate new base price aligned to grid
                    new_base_price = float(basePrice) + (steps_to_current * original_gap)
                    return (True, new_base_price, cmp)

            # No catchup needed
            return (False, basePrice, cmp)

        except Exception as e:
            print(f"Error in checkAndPlaceCatchupOrders: {e}")
            traceback.print_exc()
            return (False, basePrice, None)

    def createCatchupOrder(self, setup, missed_levels, order_type, cmp):
        """
        Creates a single catchup order to compensate for missed trades when market opens
        at a significantly different price.

        Args:
            setup: Setup configuration object
            missed_levels: Number of missed levels (used for lot size calculation)
            order_type: 'BUY' or 'SELL'
            cmp: Current Market Price

        Logic:
            - If price opened HIGH: BUY at CMP + buffer (1 order, N lots for missed trades)
            - If price opened LOW: SELL at CMP - buffer (1 order, N lots for missed trades)
        """
        try:
            userid = self.User.id
            targetId = setup.target.id
            token = setup.token
            exchange_code = setup.exchange.code
            wait = setup.wait
            count = setup.count

            user = User.objects.filter(id=userid).first()
            brokerAccount = BrokerAccount(user, targetId)
            brokerAccount.Connect(targetId, True)
            logger.debug(f'Broker Account connected for {user.username}')
            broker = Broker(brokerAccount.BrokerAccounts[0].broker.brokerId)
            if broker.canPlaceOrder(exchange_code, wait, count) == False:
                logger.warning(f'Order place timed out {user.username}:{exchange_code}:{token}')
                return []

            # Calculate buffer from CMP
            buffer = max(0.01, float(setup.stopLoss) / 10)

            if order_type == 'BUY':
                # Price opened high - place BUY slightly above CMP
                order_price = round(cmp + buffer, 2)
                lot_size = setup.lot * missed_levels  # Single lot for BUY
            else:  # SELL
                # Price opened low - place SELL slightly below CMP
                order_price = round(cmp - buffer, 2)
                lot_size = setup.lot * missed_levels  # Multiple lots for missed SELLs

            lock_key = get_redis_lock_key(userid, targetId, self.code, setup.token, exchange_code, order_type, order_price)
            # Try acquiring lock
            redis = getRedisInstance()
            if redis.set(lock_key, "1", nx=True, ex=settings.REDIS_LOCK_EXPIRY):  # Lock expires in 5 seconds
                # Direct order placement without executeOrderPairSwing
                Order = brokerAccount.submitOrder(
                    'Create', targetId, 'NORMAL', exchange_code,
                    setup.token, '', order_type, 'SL-MARKET',
                    'DELIVERY', order_price, lot_size,
                    0, 'DAY', 0, 0, 0, 0, setup.simulate,
                    wait=wait,
                    count=count,
                    remarks='ignore_callback'  # CRITICAL: Prevents follow-up orders
                )

                if not isBlankOrNone(Order.get('orderId')):
                    orderId = Order.get('orderId', '')

                    # Create log entry
                    log = self.createOrderLog(
                        userid,
                        orderId,
                        targetId,
                        Order,
                        status='OPEN', remarks="ignore_callback"
                    )

                    if log:
                        logger.info(
                            f'✅ {log.orderType} {log.exchange}:{log.symbol} '
                            f'{log.quantity} @ {log.price} [CATCHUP]'
                        )

                    return Order
                else:
                    logger.info(f'❌ {self.code} : Catchup order failed')
                    return None

        except Exception as e:
            print(f"Error in createCatchupOrder: {e}")
            traceback.print_exc()
            return None

    def createOrderLog(self, userid, orderId, brokerAccountId, verboseOrder, status='', remarks=''):
        """
        Creates or updates a SwingLog entry for an order, with details and status.
        """

        log = SwingLog.objects.filter(user_id=userid, target_id=brokerAccountId, orderId=orderId).first()
        if log:
            # log = Strategy1Log.objects.select_for_update().get(id=log.id)
            log.tradeDate = datetime.now(pytz.timezone('Asia/Kolkata'))
            log.quantity = verboseOrder['quantity']
            log.price = verboseOrder['price']
            if status != '':
                log.status = status
            log.save()

        else:
            if status == '':
                status = 'OPEN'
            log = SwingLog(
                user_id=userid,
                target_id=brokerAccountId,
                exchange=Exchanges.objects.get(code=verboseOrder['exchSeg']),
                token=verboseOrder['token'],
                symbol=verboseOrder.get('symbol', ''),
                orderId=orderId,
                tradeDate=datetime.now(pytz.timezone('Asia/Kolkata')),
                quantity=verboseOrder['quantity'],
                price=verboseOrder['price'],
                orderType=verboseOrder['tranType'],
                intraday=True if verboseOrder['variety'] == 'NORMAL' else False,
                currStock=0,
                status=status,
                orderCategory=verboseOrder['orderCategory'],
                remarks=remarks,
            )
            log.save()
        return log

    def executeOrderPairSwing(self,
                              userid, target, exchangeCode, token, numberOfOrders,
                              basePrice, lotSize, gap,
                              buyOnly=False, sellOnly=False, simulation=False, stopLoss=0, lotSizeStopLoss=0,
                              createLog=True, orderCatagory='Normal', gttBuyBuffer=0, gttSellBuffer=0, wait=0, count=1
                              ):
        """
        Places or updates a buy/sell order pair for the given setup and price/tick settings.
        Calls workerOrderPairSwing to handle actual order placement and scheduling.
        """

        broker = Broker(target.broker.brokerId)
        if True or broker.canPlaceOrder(exchangeCode, 1, 1):
            workerOrderPairSwing(self.code,
                                 userid, target.id, exchangeCode, token, numberOfOrders,
                                 basePrice, lotSize, gap, buyOnly, sellOnly,
                                 simulation, stopLoss, lotSizeStopLoss,
                                 createLog, orderCatagory, gttBuyBuffer, gttSellBuffer, wait=wait, count=count
                                 )
        else:
            t1 = Thread(target=workerOrderPairSwing, args=(self.code,
                                                           userid, target.id, exchangeCode, token, numberOfOrders,
                                                           basePrice, lotSize, gap, buyOnly, sellOnly,
                                                           simulation, stopLoss, lotSizeStopLoss,
                                                           createLog, orderCatagory, gttBuyBuffer, gttSellBuffer, wait, count
                                                           ))
            t1.start()

    def updateLogStatusFromOrderBook(self, brokerObj, orderCatagory, targetId, exchange, publish=False):
        """
        Updates SwingLog status from the broker's order book, syncing status and publishing updates if needed.
        """
        # checking actual status of the order - in case of rejection or cancelled after order is placed
        try:
            defStatus = False
            checkLog = SwingLog.objects.filter(
                user_id=self.User.id,
                target_id=targetId,
                exchange__code=exchange,
                orderCategory=orderCatagory,
                status='OPEN'
            )
            if not checkLog:
                return True

            lstOrder = brokerObj.readOrderBook(OrderCatagory=orderCatagory)
            for log in checkLog:
                for ord in lstOrder:
                    if ord['orderId'] == log.orderId and ord.get('status') != log.status and not isBlankOrNone(ord.get('status')):
                        if ord['status'] in ['REJECTED', 'CANCELED', 'COMPLETE']:
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
        """
        Resyncs strategy values (stock, price) from broker holdings, positions, and trade book.
        Updates setups with latest values.
        """
        self.getActiveSetup(exchange)

        for accountId in self.ActiveAccounts:
            brokerObj = brokerAccount.getBrokerObject(accountId)
            holdings = brokerObj.getHoldings()
            positions = brokerObj.getPositions()
            tradeBook = brokerObj.readTradeBook()
            setups = self.Setups.filter(target_id=accountId)
            for holding in holdings:
                tsyms = holding.get('exch_tsym')
                for tsym in tsyms:
                    setup = setups.filter(exchange=tsym.get('exch'), token=tsym.get('token')).first()
                    if setup:
                        setup.stockCurrent = int(tsym.get('pp'))
                        for trade in tradeBook:
                            if trade.get('exchange') == tsym.get('exch') and trade.get('token') == tsym.get('token'):
                                setup.priceCurrent = Decimal(trade.get('fillprice'))
                                setup.save()
                                break

            for position in positions:
                setup = setups.filter(exchange=position.get('exch'), token=position.get('token')).first()
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
def workerSwingOrderCallback(self, strategyCode, accId, exchange, cancelOld=True):
    """
    Worker function that subscribes to broker order queue for a given account/exchange.
    Listens for order status updates and, on successful completion, triggers the next order pair.
    Handles log updates and notifications.
    """
    accountId = int(accId)
    ba = BrokerAccounts.objects.filter(id=accountId).first()
    if not ba:
        return None
    telegram = Telegram(ba.user.id)
    telegram.sendMessage(f'Order processing for {exchange} started')
    strategy = Strategy.getStrategyInstance(ba.user, strategyCode, exchange)
    brokerAccount = BrokerAccount(ba.user, accountId)
    brokerAccount.Connect(accountId, True)
    connObj = brokerAccount.getBrokerObject(accountId)
    if connObj is None:
        telegram.sendMessage(f'Error while connecting broker account')
        logger.error(f'Error while connecting broker account for user {ba.user.username}')

    setup = strategy.Setups.filter(target_id=accountId).first()
    broker = Broker(brokerAccount.BrokerAccounts[0].broker.brokerId)
    pubsub = PubSub()
    broker_inst = broker.getBrokerInstance(brokerAccount.BrokerAccounts[0].broker.brokerId, brokerAccount.BrokerAccounts[0].id)
    if broker_inst and broker_inst.OrderQ:
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
        if ord == None:
            sleep(0.5)
            continue
        try:
            # If the order status is COMPLETE, update logs and stock, and schedule the next order pair
            print(f"callback status for ord {ord['status']}")
            if ord.get("remarks", "") == "ignore_callback":
                pubsub.clear_message()
                logger.info(f"got remark - ignore_callback, skipping order: {ord}")
                continue
            if ord.get('type', '') == 'TERMINATE':
                if ord.get('strategy', strategy.code) == strategy.code and ord.get('exchange', exchange) == exchange and ord.get('accountId', accId) == accId:
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
            logger.warning(f"callback for order {ord}")
            if ord['status'] == 'COMPLETE':
                logTrade = True
            else:
                continue
            setup = strategy.Setups.filter(exchange__code=ord['exchSeg'], token=ord['token'], target_id=accountId).first()
            if setup:
                currStock = setup.stockCurrent
            else:
                currStock = 0
                logger.error(f"No setup found for {ord['exchSeg']} : {ord['token']}")
                telegram.sendMessage(f"No setup found for {ord['exchSeg']} : {ord['token']}")
                continue
            currLog = SwingLog.objects.filter(target_id=accountId, orderId=ord['orderId']).first()
            if currLog:
                if currLog.status in ['COMPLETE']:
                    continue

                if strategy.isActive == False:  # broker.canPlaceOrder(exchange.code) and
                    continue

                originalGap = setup.gap
                originalSL = setup.stopLoss
                oldQty = currStock
                # Determine lot sizes based on position
                lotSizeBuy = setup.lot
                lotSizeStopLoss = setup.slLot if setup.useSlLot else setup.lot

                triggerPrice = Decimal(ord.get('triggerPrice'))
                basePrice = triggerPrice if triggerPrice is not None else Decimal(ord.get('tradePrice', ord.get('limitPrice', currLog.price)))

                # Update stock current based on order type
                if ord['tranType'] == 'BUY':
                    gap = originalGap
                    stopLoss = originalSL
                    currStock += currLog.quantity
                else:
                    gap = originalSL
                    stopLoss = originalGap
                    currStock -= currLog.quantity
                print(f"ordertype {ord['tranType']}@{basePrice}, original gap {originalGap}, original SL {originalSL}, oldQty {oldQty}, currStock {currStock}")

                if oldQty > 0:
                    # trend was UP
                    if ord['tranType'] == 'BUY':
                        print("continue buying in increasing order")
                        gap = originalGap
                        stopLoss = originalSL
                    else:
                        # market flips DOWN
                        basePrice = triggerPrice - originalGap + originalSL
                        if currStock == 0:
                            print("market flipped to sell, curr stock zero")
                            gap = originalGap
                            stopLoss = originalGap
                        else:
                            print("market flipped to sell, curr stock non zero still using the same SL and gap")
                            gap = originalGap
                            stopLoss = originalSL

                elif oldQty < 0:
                    # trend was DOWN
                    if ord['tranType'] == 'SELL':
                        print("continue selling in decreasing order")
                        gap = originalSL
                        stopLoss = originalGap
                    else:
                        # flips UP
                        basePrice = triggerPrice + originalGap - originalSL
                        if currStock == 0:
                            print("market flipped to buy, curr stock zero")
                            gap = originalGap
                            stopLoss = originalGap
                        else:
                            print("market flipped to buy, curr stock non zero")
                            gap = originalSL
                            stopLoss = originalGap

                print(f"updated gap {gap}, SL {stopLoss}, basePrice {basePrice}, triggerPrice {triggerPrice}")
                setup.priceCurrent = basePrice  # base Price is aware of the market trend
                setup.stockCurrent = currStock
                setup.lastExecutedOrderType = ord['tranType']
                currLog.status = ord.get('status')
                currLog.currStock = currStock
                currLog.updatedOn = datetime.now(pytz.timezone('Asia/Kolkata'))
                currLog.save()
                setup.save()
                message = f"User Order: {ba.user}, {ord['tranType']}-{setup.exchange.code} - Qty ( {currLog.quantity} @ {basePrice} ) currStock: {currStock}"
                telegram.sendMessage(message)
                logger.info(message)
                print(message)

                # Schedule the next order pair
                if logTrade and setup:
                    buyOnly = False
                    sellOnly = False

                    if setup.stockCurrent >= setup.stockMax:
                        sellOnly = True
                    if setup.stockCurrent <= setup.stockMin:
                        buyOnly = True
                    logger.debug(f'work order pair initiating for {setup.exchange.code}:{setup.token} {basePrice}')
                    if broker.canPlaceOrder(exchange):
                        workerOrderPairSwing(strategy.code, strategy.User.id, setup.target.id, setup.exchange.code, setup.token, 1,
                                             basePrice, lotSizeBuy, gap,
                                             buyOnly, sellOnly, setup.simulate, stopLoss, lotSizeStopLoss)
                    else:
                        t1 = Thread(target=workerOrderPairSwing,
                                    args=(
                                        strategy.code, strategy.User.id, setup.target.id, setup.exchange.code, setup.token, 1,
                                        basePrice, lotSizeBuy, gap,
                                        buyOnly, sellOnly, setup.simulate, stopLoss, lotSizeStopLoss
                                    )
                                    )
                        t1.start()

                    logger.debug(f'work order pair completed for {setup.exchange.code}:{setup.token} {basePrice}')
        except Exception as exc:
            traceback.print_exc()
            logger.error(exc)

    telegram.sendMessage(f'Process for Exchange {exchange} is completed')
    sendTradesbyEmail.delay(strategy.User.id, exchange.code if hasattr(exchange, 'code') else "")
    telegram.sendMessage(f'Email with trade list for Exchange {exchange} is sent')


@shared_task(bind=True)
def sendTradesbyEmail(self, userid, exchange, logDate=''):
    """
    Sends an email to the user with the trade log for the given date and exchange.
    Generates an Excel file and emails it to the user's registered address.
    """
    qFilter = Q(user_id=userid, exchange__code=exchange)

    if logDate == '':
        objLogDate = datetime.now()
    else:
        objLogDate = datetime.strptime(logDate, "%Y%m%d")

    qFilter &= Q(tradeDate__date=objLogDate.date())
    logs = SwingLog.objects.filter(qFilter).order_by('exchange', 'token', 'tradeDate')
    user = User.objects.filter(id=userid).first()
    social = UserSocialProfile.objects.filter(user=user).first()
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
        body = f'''
                Dear  {user.first_name},
                Enclosed the trade log for the subject date. 
                Trade log is for reference and do not claim to be absolutely true.
                In case you find any issue please reply to this mail.

                Thanks, 
                Team Dhananjay'
                '''
        emailto = [social.email]

        email.send(subject, body, emailto, excelfile, f"tradeLog{objLogDate.strftime('%d%m%Y')}.xls", 'application/ms-excel')


def getOrder(lstOrder: list, orderId: str):
    """
    Utility to find and return an order from a list by orderId.
    """
    for ord in lstOrder:
        if ord.get('orderId') == orderId:
            return ord

    return None


def getOrderWithStatus(lstOrder: list, orderId: str, status: str):
    """
    Utility to find and return an order from a list by orderId.
    """
    for ord in lstOrder:
        if ord.get('orderId') == orderId and ord.get('status') == status:
            return ord

    return None


def get_redis_lock_key(userid, targetId, strategyCode, token, exchange, tranType, price):
    """
    Utility to generate a Redis lock key for order placement, preventing duplicates.
    """
    hash_input = f"{userid}:{targetId}:{strategyCode}:{token}:{exchange}:{tranType}:{price}"
    return f"lock:orderpair:{hashlib.md5(hash_input.encode()).hexdigest()}"


@shared_task(bind=True)
def workerOrderPairSwing(self,
                         strategyCode, userid, targetId, exchange, token, numberOfOrders,
                         basePrice, lotSize, gap,
                         buyOnly=False, sellOnly=False, simulation=False, stopLoss=0, lotSizeStopLoss=0,
                         createLog=True, orderCatagory='Normal', gttBuyBuffer=0, gttSellBuffer=0, wait=0, count=1, remarks=""
                         ):
    """
    Worker function to place or update buy/sell order pairs for a given account/token.
    Calculates next buy/sell prices based on tick settings and places orders if not already open.
    Uses Redis locks to prevent duplicate orders.
    """
    try:
        telegram = Telegram(userid)
        user = User.objects.filter(id=userid).first()
        strategy = Strategy.getStrategyInstance(user, strategyCode, exchange)
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
        # if tickSizeSell == 0:
        #     tickSizeSell = tickSizeBuy
        #
        # if lotSizeSell == 0:
        #     lotSizeSell = lotSizeBuy

        orderId = ''
        # Check for any Open Orders
        checkLog = SwingLog.objects.filter(
            user_id=userid,
            target_id=targetId,
            exchange__code=exchange,
            token=token,
            orderCategory=orderCatagory,
            status='OPEN'
        )
        # checking actual status of the order - in case of rejection or cancelled after order is placed
        lstOrder = brokerObj.readOrderBook(OrderCatagory=orderCatagory)
        for log in checkLog:
            for ord in lstOrder:
                if ord['orderId'] == log.orderId and ord.get('status') != log.status and not isBlankOrNone(ord.get('status')):
                    log.status = ord.get('status')
                    log.save()
                    logger.debug(f"order status for orderid {log.orderId} updated to {ord.get('status')}")

        checkLog = SwingLog.objects.filter(
            user_id=userid,
            target_id=targetId,
            exchange__code=exchange,
            token=token,
            orderCategory=orderCatagory,
            status='OPEN', remarks=''
        ).order_by('-tradeDate', '-updatedOn')

        buyLog = checkLog.filter(orderType='BUY').first()
        sellLog = checkLog.filter(orderType='SELL').first()

        buyPrice = round(float(basePrice) + (float(gap)), 2)
        sellPrice = round(float(basePrice) - (float(stopLoss)), 2)
        print(f"new buyPrice: {buyPrice}, sellPrice: {sellPrice}" + f"buyLog: {buyLog} " if buyLog else f"sellLog: {sellLog} " + f"buyOnly order" if buyOnly else f"sellOnly order")
        if sellOnly == False:
            log = buyLog
            if log:
                lstOrder = brokerObj.readOrderBook(log.orderId, orderCatagory)

                # order = lstOrder[0]
                order = getOrderWithStatus(lstOrder, log.orderId, 'OPEN')
                if order:
                    if order.get('status') in ['OPEN']:
                        action = 'Update'
                        orderId = log.orderId
                    else:
                        action = 'Create'
                        orderId = 0
                else:
                    action = 'Create'
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
            lock_key = get_redis_lock_key(userid, targetId, strategyCode, token, exchange, 'BUY', buyPrice)
            # Try acquiring lock
            if redis.set(lock_key, "1", nx=True, ex=settings.REDIS_LOCK_EXPIRY):  # Lock expires in 5 seconds
                Order = brokerAccount.submitOrder(action, targetId, orderCatagory.upper(), exchange, token, '',
                                                  'BUY', 'SL-MARKET', 'DELIVERY', buyPrice, lotSize, 0, 'DAY', 0, 0, 0, orderId, simulation, wait=wait, count=count, remarks=remarks)
                if not isBlankOrNone(Order.get('orderId')):
                    orderId = Order.get('orderId', '')
                    lstOrderBook = brokerAccount.readOrderBook(targetId, orderId, orderCatagory)
                    if len(lstOrderBook) > 0:
                        logger.debug(f'order created with id {orderId}')
                        # strategy.createOrderLog(strategy.User.id, orderId, target.id, Order, status = lstOrderBook[0].get('status',''))
                        log = strategy.createOrderLog(strategy.User.id, orderId, targetId, Order, status='OPEN')
                        logger.debug(f'order updated in log for id {orderId} action {action}')
                        if log:
                            telegram.sendMessage(f'{log.orderType} {log.exchange}:{log.symbol}-{log.quantity}@{log.price}')
                    lstOrd.append(Order)
            else:
                logger.warning(f"Skipping duplicate workerOrderPairSwing task for {token}")

        if buyOnly == False:

            log = sellLog
            if log:
                lstOrder = brokerAccount.readOrderBook(targetId, log.orderId, OrderType='All')
                ord = getOrderWithStatus(lstOrder, log.orderId, 'OPEN')
                if ord:
                    if ord.get('status') in ['OPEN']:
                        action = 'Update'

                        orderId = log.orderId
                    else:
                        action = 'Create'
                        orderId = 0
                else:
                    action = 'Create'
                    logger.error(f'order not found in order book {log.orderId} token {token}')
            else:
                action = 'Create'
                orderId = 0

            lock_key = get_redis_lock_key(userid, targetId, strategyCode, token, exchange, 'SELL', sellPrice)
            # Try acquiring lock
            if redis.set(lock_key, "1", nx=True, ex=settings.REDIS_LOCK_EXPIRY):  # Lock expires in 5 seconds
                logger.debug(f'sell order processing started with action {action}')
                Order = brokerAccount.submitOrder(action, targetId, 'NORMAL', exchange, token, '',
                                                  'SELL', 'SL-MARKET', 'DELIVERY', sellPrice, lotSizeStopLoss, 0, 'DAY', 0, 0, 0, orderId, simulation, wait=wait, count=count, remarks=remarks)

                if not isBlankOrNone(Order.get('orderId')):
                    orderId = Order.get('orderId', '')
                    # if lstOrder[0]['orderStatus'] == ['OPEN','PENDING','COMPLETE']:
                    lstOrderBook = brokerAccount.readOrderBook(targetId, orderId, orderCatagory)
                    if len(lstOrderBook) > 0:
                        logger.debug(f'order created with id {orderId}')
                        # strategy.createOrderLog(strategy.User.id, orderId, target.id, Order, status = lstOrderBook[0].get('status',''))
                        log = strategy.createOrderLog(strategy.User.id, orderId, targetId, Order, status='OPEN')
                        logger.debug(f'order updated in log for id {orderId} action {action}')
                        if log:
                            telegram.sendMessage(f'{log.orderType} {log.exchange}:{log.symbol}-{log.quantity}@{log.price}')
                    lstOrd.append(Order)

                    # return lstOrd
    except Exception as e:
        print(e)
        traceback.print_exc()
