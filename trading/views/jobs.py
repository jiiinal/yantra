from trading.Strategies.strategyManager import StrategyManager
from django.http import HttpResponse, JsonResponse
from trading.NorenRestApiPy.api_helper import NorenApiPy
from trading.models import BrokerAccounts, Scripts
from trading.Entities.BrokerAccounts.brokerAccount import BrokerAccount
from userauth.views import get_user
import pyotp
import logging
from trading.Redis.pubsub import PubSub
from trading.Entities.Brokers.broker import Broker
from celery import shared_task
from time import sleep
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from trading.Strategies.jobbing import sendTradesbyEmail
from datetime import datetime
import time
logger = logging.getLogger(__name__)

@shared_task(bind = True)
def workerStartStrategyForAll(self):
    try:
        users = get_user()
        for user in users:
            startStrategyForUser.delay(user.id)
        return True
    except Exception as e:
        print(str(e))

@api_view(["POST"])
def startStrategy(request):
    try:
        startStrategyForUser(request.user.id)
        # return HttpResponse(f'Stragey started {request.user.username}')
        return Response({'message': f'Stragey started {request.user.username}'}, status=status.HTTP_200_OK)
    except Exception as e:
        # return HttpResponse(f'Strategy start error for {request.user.username}:{e.args[0]}')
        return Response({'message': f'Stragey start error for {request.user.username}'}, status=status.HTTP_400_BAD_REQUEST)
    

def terminateUserProcess(user):
    try:
        ba = BrokerAccount(user)
        if ba:
            broker = Broker(Broker.FINVASIA)
            pubsub = PubSub()
            QueueId = broker.getQueueId('Q',user.id,'O')
            logger.debug(f'Terminate: QID {QueueId}')
            for acc in ba.BrokerAccounts:

                data = {'type':'TERMINATE','accountId': acc.id}
                pubsub.publish(QueueId,data)
                logger.debug(f'Terminate: Published: QID {QueueId}, data: {data}')
            sleep(2)
            return True
    except Exception as e:
        logger.debug(f'terminateUserProcess Error {str(e)}')
        return False
    
@api_view(["POST"])    
def terminateStrategy(request):
    try:
        if terminateUserProcess(request.user):
    
            return Response({'message': f'Strategy Terminated for {request.user.username}'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': f'Stragey Termination error for {request.user.username}'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'message': f'Stragey Termination error for {request.user.username}'}, status=status.HTTP_400_BAD_REQUEST)

@shared_task(bind=True)        
def startStrategyForUser(self, userid=None):

    try:
        users = get_user(userid)
        
        for user in users:
            logger.debug(f'user {user.username}')
            terminateUserProcess(user)
            logger.info(f'strategy master started {user.username}')

            manager = StrategyManager(user)
            # logger.error(f'error {request.user}')d
            logger.info(f'strategy master start: initiate {user.username}')

            manager.initiate()
            logger.info(f'strategy master end : initiate {user.username}')

            logger.debug(f'strategy master starting {user.username}')
            manager.start()

            logger.debug(f'strategy master started {user.username}')

        return HttpResponse('start strategy completed')
    
    except Exception as e:

        logger.debug(f'startStrategyForUser {str(e)}')


@api_view(['GET'])
def getSymbols(request):
    
    if request.method != 'GET':

        return Response({'status': 'error','message':'Invalid request method'}, status=status.HTTP_400_BAD_REQUEST)    
    
    else:
        data = request.data
        if data == {} or data == None:
            data = request.GET            
        exchange = data.get('exchange')
        broker = int(data.get('broker'))
        if exchange and broker:
            try:
                broker = Broker(broker)
                symbols = broker.getScriptByExchange(exchange)
            except Exception as e:
                return Response([], status=status.HTTP_400_BAD_REQUEST)        
        else:
            return Response([], status=status.HTTP_200_OK)

        if not symbols:
            return Response([], status=status.HTTP_200_OK)
        return Response(list(symbols.values()), status=status.HTTP_200_OK)

def convert_to_timestamp(date_str):
    """
    Converts a date string in MM-DD-YYYY format to a Unix timestamp (in seconds).
    Example input: '06-19-2024'
    """
    try:
        # Parse the date string to datetime object
        dt = datetime.strptime(date_str, '%d-%m-%Y')
        # Convert to Unix timestamp
        return int(time.mktime(dt.timetuple()))
    except ValueError:
        raise ValueError("Date must be in MM-DD-YYYY format")
    

@api_view(['GET'])
def getTimeSeriesData(request):
    try:

        qury_params = request.query_params
        if qury_params == {} or qury_params == None:
            qury_params = request.GET

        if qury_params == {} or qury_params == None:
            qury_params = request.data

        if qury_params == {} or qury_params == None:
            return Response({'status': 'error','message':'invalid query param'}, status=status.HTTP_400_BAD_REQUEST)

        ba = BrokerAccount(request.user)    
        acc = ba.BrokerAccounts.first()
        ba.Connect(acc.id)
        bo = ba.getBrokerObject(acc.id)

        EXCHANGE = qury_params.get('exchange')
        TOKEN = str(qury_params.get('token'))    
            
        START_DATE = convert_to_timestamp(qury_params.get('startdate'))
        END_DATE = convert_to_timestamp(qury_params.get('enddate'))
        INTERVAL = qury_params.get('interval')

        timedata = bo.ConnectionObject.get_time_price_series(
                            EXCHANGE, TOKEN, starttime=START_DATE, endtime=END_DATE, interval= INTERVAL
                            )
        return Response({'status': 'sucess','message':timedata}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'status': 'error','message':str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def testConnection(request):
    if request.method != 'POST':
        return Response({'status': 'error','message':'Invalid request method'}, status=status.HTTP_400_BAD_REQUEST)
    
    else:
        ba = BrokerAccount(request.user)
        id = int(request.data.get('id'))
        logger.debug('Test connection started',request.user)
        ba.Connect(id)
        logger.debug('Test connection completed',request.user)
        bo = ba.getBrokerObject(id)
        try:
            quote = bo.ConnectionObject.get_quotes('NSE','2885')
            if quote:
                logger.debug('Test connection success {request.user}')
                return Response({'status': 'success','message':f'Test Connection Sucess for {bo.Account.nickName}'}, status=status.HTTP_200_OK)
            else:
                logger.debug('Test connection error {request.user} {e.args[0]}')
                return Response({'status': 'error','message':'Test Connection error'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'status': 'error','message':str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
@api_view(['POST'])
def temp(request):
    if request.method != 'POST':
        return Response({'status': 'error','message':'Invalid request method'}, status=status.HTTP_400_BAD_REQUEST)
    
    else:
        sendTradesbyEmail(request.user.id,'All','2025-01-01','2025-01-01')
        return Response({'status': 'success','message':'Email sent'}, status=status.HTTP_200_OK)