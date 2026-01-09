from trading.Strategies.jobbing import Jobbing
from trading.Strategies.strategy import Strategy
from trading.Entities.BrokerAccounts.brokerAccount import BrokerAccount
from utils.views import getUniqueStruct, getItemByKey
from trading.models import Strategis
# from trading.views.Redis.distributor import Distributor
from trading.Entities.Report.historicalData import HistoricalData
# from trading.views.jobs import terminateUserProcess
# from trading.Redis.redisdb import RedisDB

# activeScript = {
#     'accountId' : setup.target.id,
#     'brokerId': setup.target.broker.brokerId,
#     'exchange': setup.exchSeg,
#     'token': setup.token,
#     'symbol': setup.symbol
# }
import logging
logger = logging.getLogger(__name__)

class StrategyManager():
    '''
    Strategy Manager is an overall central component that manages all the strategy for a user
    it contains all the objects relevant objeccts viz. all strategy objects with setup, all borker account and broker conneciton to perform its task.
    '''
    def __init__(self, user, code=None) -> None:
        '''
        initialize manager with optional strategy code. 
        strategy coe is used to instantiate object for specific strategy and perform operations without affecting other strategy in place.
        '''
        self.User = user        
        self.code = code

    def getActiveStrategies(self, exchange=None):
        '''
        getting all strategy objects and relavant setups as dictionary
        '''

        lstActiveStrategies = []
        lstActiveScripts = []

        strategies = Strategis.objects.all()
        if self.code:
            strategies = strategies.filter(code = self.code)

        for strat in strategies:
            strategy = Strategy.getStrategyInstance(self.User, strat.code, exchange)
            if strategy:
                if strategy.isActive:
                    lstActiveStrategies.append(strategy)
       
            
        for strategy in lstActiveStrategies:
            for script in strategy.ActiveScripts:
                if script not in lstActiveScripts:
                    lstActiveScripts.append(script)

        if exchange:
            self.exchange = exchange
            lstTemp = lstActiveScripts
            lstActiveScripts = []
            for script in lstTemp:
                if script['exchange'] == exchange:
                    lstActiveScripts.append(script) 

        self.ActiveStrategies = lstActiveStrategies
        self.ActiveScripts = lstActiveScripts
        # redisDB = RedisDB(self.User, True)
        
        # redisDB.setlist(self.ActiveScripts,'script',['accountId','exchange','token'])

        return lstActiveStrategies

    def subscribeWebSockets(self):
        '''
        subscribe to the websocket for getting messages for Order update or/and price changes
        this will subscribe to the sockets depending on the respective strategies settings. 
        The sockets read the input and publish it over the redis pubsub. user broker object QueueId to subscribe to
        '''
        logger.debug(f'start: Websocket subscription {self.User} strategy [{self.code}]')

        lstTicks = self.TicksForCallback
        lstUnique = getUniqueStruct(lstTicks) #accountId
        for strategy in self.ActiveStrategies:
            for accountId in strategy.ActiveAccounts:
                brokerObj = self.brokerAccount.getBrokerObject(accountId)
                brokerObj.subscribeWebSockets(strategy.requireOrderCallback, getItemByKey(lstUnique,'accountId', accountId))

        logger.debug(f'End: Websocket subscription {self.User} strategy [{self.code}]')
    
    def initiate(self, exchange=None, subscribe=True):
        try:
            lstTicks = []
            lstTickForCallback = []
            self.getActiveStrategies(exchange)
            brokerAcc = BrokerAccount(self.User)
            brokerAcc.Connect()
            self.brokerAccount = brokerAcc
            
            # # cancelling old orders
            # for account in self.brokerAccount.BrokerAccounts:
            #     ba = self.brokerAccount.getBrokerObject(account.id)
            #     ba.cancelOrders([])

            for strategy in self.ActiveStrategies:
                strategy.initiate()
                ticks = strategy.getScriptForTickCallback()
                logger.debug(f'Ticks {ticks}')
                for tick in ticks:
                    lstTicks.append(tick)
            self.TicksForCallback = lstTicks
            if subscribe:
                self.subscribeWebSockets()        
        except Exception as e:
            logger.debug(f'initiate Error {str(e)}')
    
    def start(self, exchange=None):

        # dist = Distributor(self.User,self.ActiveScripts)
        # dist.startDistribution(self.ActiveScripts)
    
        for strategy in self.ActiveStrategies:
            strategy.start(self.brokerAccount, exchange)

    def resyncStrategyValues(self, exchange=None):

        for strategy in self.ActiveStrategies:
            strategy.resyncStrategyValues(self.brokerAccount, exchange)

    def getHistoricalData(self, accountId,exchSeg,symbol,token,fromdate,todate, interval):
        hist = HistoricalData(self.brokerAccount, accountId)
        histData = hist.getHistoricCandleData(exchSeg, token, fromdate, todate, 0, interval,symbol)
        return histData

