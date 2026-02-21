import redis
import simplejson as myjson
from datetime import datetime
import pytz
from django.conf import settings
import logging
logger = logging.getLogger(__name__)

def getRedisInstance(decode=False):
    try:
        if settings.REDIS_PASSWORD:
            r = redis.Redis(host='localhost', port=6379, db=0,password=settings.REDIS_PASSWORD, decode_responses=decode)
            # logger.info('Pubsub with password')
        else:
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=decode)    

        return r
    
    except Exception as e:
        logger.error(f'error conn redis {e.args[0]}')
        return None


class PubSub():
    def __init__(self, channel=None,decode=False):
        # logger.info('Pubsub initiated start')
        self.Redis = getRedisInstance(decode)
        self.pubsub = self.Redis.pubsub()        
        self.channel = channel
        self.decode = decode
        # logger.info('Pubsub initiated completed')
    def publish(self, channel, data):
        if not self.decode:
            data = myjson.dumps(data)

        self.Redis.publish(channel, data)
        return True
    
    def subscribe(self, channels):
        print("subscribed to channels", channels)
        # "my-channel-1", "my-channel-2"
        self.pubsub.subscribe(channels)
        return True
    
    def get_message(self):
        # {'type': 'message', 'pattern': None, 'channel': b'my-channel-1', 'data': b'{"a": "aaa", "b": "bbbb"}'}
        try:
            message = self.pubsub.get_message()
            if message is not None and message.get('type') == 'message':
                if not self.decode:                
                    message = myjson.loads(message.get('data'))                        
                    # message['data'] = myjson.loads(message.get('data'))                        
            else:
                message = None
            return message
        
        except Exception as e:
            logger.error(f'err{e.args[0]}')    

    def clear_message(self):
        
        try:

            while not self.pubsub.get_message() == None:
                pass
                    
        except Exception as e:
            logger.debug(e)
        finally:
            return True
    
    def unsubscribe(self, channels):
        self.pubsub.unsubscribe(channels)
        return True
    
    # @property
    def getLastAccess(self, channel = None):
        # https://roman.pt/posts/time-series-caching/
        if channel == None:
            channel = self.channel
        try:            
            return datetime.strptime(myjson.loads(self.Redis.get(channel+':a')), '%Y-%m-%d %H:%M:%S.%f%z')
        except Exception:
            return None

    # @lastAccess.setter
    def setLastAccess(self,channel = None):
        # https://roman.pt/posts/time-series-caching/
        if channel == None:
            channel = self.channel
        channel = "".join(channel)
        self.Redis.set(channel+':a',str(datetime.now(pytz.timezone('Asia/Kolkata'))))
