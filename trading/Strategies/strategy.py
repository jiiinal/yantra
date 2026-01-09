from trading.models import StrategyStatus, Strategis

import importlib
import logging
logger = logging.getLogger(__name__)

def getStrategyQueueId(MasterQueue, clientId,exchange, type='O'): # O-Order, T-Tick
    return f'{MasterQueue}:{clientId}:{exchange}:{type}'

class Strategy():
    def __init__(self, user) -> None:
        self.User = user
        self.code = None
        self.StrategyMaster = None
        self.ActiveAccounts = []
        self.Setups = None

    @staticmethod
    def getStrategyInstance(user, code, exchange):
        instance = None
        try:
            st = Strategis.objects.filter(code = code).first()
            if st:
                module = importlib.import_module('trading.Strategies.' + st.className.lower())
                class_ = getattr(module, st.className)
                instance = class_(user, exchange)   
        except Exception as e:
            logger.debug(e)
        finally:
            return instance

    def getActiveSetup(self):
        raiseParentFunctionCall()

    @property
    def isActive(self, user = None):
        if not self.StrategyMaster.isActive: #check in the master table
            return False
        
        if not user:
            user = self.User
        
        if user == None:
            raise Exception(f'No user defined for strategy code {self.code}')

        setups = self.getActiveSetup()        
        return setups != None
       
    @property
    def requireOrderCallback(self):
        return True

    @property
    def requireTickCallback(self):
        return False
    
    def getScriptForTickCallback(self):
        # it should be in the format of {'accountId': {accountId}, 'exchange': {exchange}, 'token': {token}, 'symbol':{symbol}}
        return []
        
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
        status.save()
        
    def initiate(self):
        raiseParentFunctionCall()
    
    def start(self):
        raiseParentFunctionCall()

    def processOrderCallback(self, defOrderCallback, **args):
        raiseParentFunctionCall()

    def processTickCallback(self, defTickCallback, **args):
        raiseParentFunctionCall()

    def createOrderLog(self, userid, orderId, brokerAccountId, verboseOrder, status = ''):    
        raiseParentFunctionCall()

def raiseParentFunctionCall():
    raise Exception('Parent method called, please redefine the method in child class')
