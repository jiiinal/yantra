# from trading.views.broker import Broker
from trading.models import BrokerAccounts

from trading.Entities.Brokers.broker import Broker
from trading.Entities.Brokers.bnrathi import BNRathi
from django.db.models import Q
# from mainapp.views.logger import logging
import datetime
import logging

logger = logging.getLogger(__name__)


class BrokerAccount():
    # create object for each broker accounts and store as class variable
    def __init__(self, user, accountId=None) -> None:
        qFilter = Q(user=user)
        if accountId:
            qFilter &= Q(id=accountId)
        self.User = user
        self.BrokerAccounts = BrokerAccounts.objects.filter(qFilter)
        self.AccountId = accountId

    def getAccountByClientId(self, clientId):
        return self.BrokerAccount.filter(clientId=clientId)

    def getAccountByNickName(self, nickName):
        return self.BrokerAccount.filter(nickName=nickName)

    def getAccount(self, accountId=None):
        if accountId is None:
            accountId = self.AccountId
        if accountId:
            return self.BrokerAccounts.filter(id=accountId)
        else:
            return self.BrokerAccounts

    def setDefaultAccountId(self, accountId) -> None:
        self.AccountId = accountId
        self.BrokerAccount = self.getAccount(accountId)

    @property
    def DefaultAccount(self):
        return self.BrokerAccount.filter(id=self.AccountId)

    # def getTOTP(self, accountId = None) -> int:
    #     account = self.getAccount(accountId)
    #     if account:
    #         totp = pyotp.TOTP(account.factor2Secret)
    #         return totp.now()
    #     else:
    #         raise Exception('No Default/Specific Account found ')

    def Connect(self, accountId=None, sessionOnly=False):
        logging.debug(f'connection attempted for Account Id {accountId}')
        lstBrokerObject = []
        accounts = self.getAccount(accountId)
        for account in accounts:
            if account.broker.brokerId in [Broker.BNRATHI, Broker.FINVASIA]:
                brokerObject = BNRathi(account.broker.brokerId, account.id)
                connobj = brokerObject.getConnectionObject(sessionOnly)
                lstBrokerObject.append(brokerObject)
                if connobj:
                    logger.debug(f'Broker Account connected for Account {brokerObject.Account.nickName}')
                else:
                    logger.debug(f'Broker Account failed to connect for Account {brokerObject.Account.nickName}')

        self.BrokerObjets = lstBrokerObject

    def getBrokerObject(self, accountId):
        if self.BrokerObjets == None:
            raise Exception('No Broker Objects, did you call Connect to get the broker objects?')
        for object in self.BrokerObjets:
            if object.Account.id == accountId:
                return object

    def getHistoricalData(self, accountId, exchSeg, symbol, token, fromdate, todate, interval="1"):
        brokerObject = self.getBrokerObject(accountId)
        return brokerObject.getHistoricalData(exchSeg, symbol, token, fromdate, todate, interval)

    def readOrderBook(self, accountId, orderId='', OrderType='All'):
        # OrderType = 'All', 'GTT','Normal'
        brokerObj = self.getBrokerObject(accountId)
        lstOrderBook = []

        orderBook = brokerObj.readOrderBook(orderId, OrderType)
        for order in orderBook:
            lstOrderBook.append(order)

        self.orderBook = lstOrderBook
        return lstOrderBook

    def getPositions(self, accountId):
        brokerObj = self.getBrokerObject(accountId)
        positions = brokerObj.getPositions()
        return positions

    def readTradeBook(self, accountId, orderId=''):
        brokerObj = self.getBrokerObject(accountId)
        lstTradeBook = []

        tradeBook = brokerObj.readTradeBook(orderId)
        for trade in lstTradeBook:
            lstTradeBook.append(trade)

        self.tradeBook = lstTradeBook
        return lstTradeBook

    def VerboseOrder(
            self, variety, exchange, token, symbol, tranType, priceType, prodType, price, quantity,
            disclQty, validity='DAY', stopPrice=0, stopLoss=0, takeProfit=0, orderId='', orderCatoery='Normal', gttBuyBuffer=0, gttSellBuffer=0):
        lstVerbose = []
        for obj in self.BrokerObjets:
            lstOrder = obj.VerboseOrder(
                variety, exchange, token, symbol, tranType, priceType, prodType, price, quantity, disclQty, validity, stopPrice, stopLoss, takeProfit, orderId,
                orderCatoery, gttBuyBuffer, gttSellBuffer
            )
            for order in lstOrder:
                lstVerbose.append(order)
        return lstVerbose

    def StarndardOrder(
            self, variety, exchange, token, symbol, tranType, priceType, prodType, price, quantity,
            disclQty, validity='DAY', stopPrice=0, stopLoss=0, takeProfit=0, orderId='',
            orderCategory='Normal', gttBuyBuffer=0, gttSellBuffer=0, remarks=""):
        broker = Broker(0)
        script = broker.getScript(exchange, token, symbol)

        if script == None:
            return

        if (exchange == 'CDS' or exchange == 'MCX') and prodType == 'DELIVERY':
            prodType = 'MARGIN'

        tsymb = script.symbol

        # if priceType == 'MARKET':
        #     price = 0

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
            "gttSellBuffer": gttSellBuffer,
            "remarks": remarks
        }

        return order

    def cancelOrders(self, accountId, brokerId, exchange='MCX', orders: list = []):
        try:
            broker = Broker(brokerId)
            if broker.canPlaceOrder(exchange, 60, 15) == False:
                return []
            brokerObj = self.getBrokerObject(accountId)
            brokerObj.cancelOrders(orders)
        except Exception as e:
            print(str(e))
        finally:
            return True

    def getHoldings(self, accountId, product_type=None):
        brokerObj = self.getBrokerObject(accountId)
        return brokerObj.getHoldings(product_type)

    def submitOrder(self, action, accountId, variety, exchange, token, symbol, tranType, priceType, prodType, price, quantity,
                    disclQty, validity='DAY', stopPrice=0, stopLoss=0, takeProfit=0, orderId='', simulation=False,
                    orderCatoery='Normal', gttBuyBuffer=0, gttSellBuffer=0, wait=0, count=1, remarks=""):

        standardOrder = self.StarndardOrder(
            variety, exchange, token, symbol, tranType, priceType, prodType, price, quantity,
            disclQty, validity, 0, stopLoss, takeProfit, orderId,
            orderCatoery, gttBuyBuffer, gttSellBuffer, remarks=remarks)
        if not standardOrder:
            return []
        if simulation:

            orderId = datetime.now().strftime('%Y%m%d%H%M%S%f')
            standardOrder['orderId'] = orderId
            standardOrder['status'] = 'OPEN'

        else:
            brokerObj = self.getBrokerObject(accountId)
            lstStandardOrder = [standardOrder]
            lstOrderParam = brokerObj.prepareOrderParams(action, lstStandardOrder)

            broker = Broker(brokerObj.BrokerId)
            if broker.canPlaceOrder(exchange, wait, count) == False:
                return []

            if action.upper() == 'CREATE':
                lstOrd = brokerObj.createOrders(lstOrderParam)
                if lstOrd:
                    orderId = lstOrd[0]['orderId']
                    standardOrder['orderId'] = orderId
                    standardOrder['status'] = 'OPEN'

            if action.upper() in ['MODIFY', 'UPDATE', 'CHANGE']:
                lstOrd = brokerObj.modifyOrders(lstOrderParam)
                if lstOrd:
                    orderId = lstOrd[0]['orderId']
                    standardOrder['orderId'] = orderId
                    standardOrder['status'] = 'OPEN'

        return standardOrder
