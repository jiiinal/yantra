from trading.models import  Strategis
from social.views.telegram import Telegram
from trading.Strategies.strategy import Strategy

from trading.Redis.pubsub import PubSub
from trading.Redis.pubsub import getRedisInstance

STRATEGY_CODE = 'UPDOWN'



class SnaksAndLadder(Strategy):
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
        # self.MasterQueue = 'DUMMY'
        self.PubSub = PubSub()