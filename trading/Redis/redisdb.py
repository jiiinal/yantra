import redis
from django.conf import settings
import logging
logger = logging.getLogger(__name__)

class RedisDB():
    def __init__(self, userid, decode=True):
        if settings.REDIS_PASSWORD:
            self.Redis = redis.Redis(host='localhost', port=6379, db=0,password=settings.REDIS_PASSWORD, decode_responses=decode)
        else:
            self.Redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=decode)
        self.decode = decode
        self.userid = userid

    def clean_data(self, record):
        """Ensure no NoneType values exist in the record before storing in Redis."""
        return {k: (v if v is not None else "") for k, v in record.items()}

    def setlist(self, data:list,model:str,key=['id']):
        try:
            iCount = 0
            
            for record in data:
                record = self.clean_data(record)
                lstr = ''
                for k in key:
                    lstr += '_' + str(record[k])
                key_val = model + lstr # Creating a unique key for each entry

                self.Redis.hset(name=key_val, key = model, value=key_val, mapping=record)            
                iCount+= 1

            return iCount
        except Exception as e:
            logger.error(e.args[0])    
            return None
        
    def getlist(self,record:dict,model:str,key=['id']):
        try:
            str = model
            for k in key:
                str += '_' + record[k]
            key_val = 'model' + str # Creating a unique key for each entry
            data = self.Redis.hgetall(key_val)
            return data
        except Exception as e:
            Logger.error(e)
            return None
