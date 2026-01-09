# web.telegram.og

# botfather

# /newbot
# https://api.telegram.org/bot5485321748:AAFDKGI1dmeibyY_gaH9LcsYFchJUwlIyAQ/getUpdates
import telepot
import requests
import json
import datetime
from django.contrib.auth.models import User
from social.models import UserSocialProfile
from trading.views.cacheRoutines import getUserSocialProfile
from threading import Thread
# from trading.views.Broker import Broker
from trading.views.cacheRoutines import CACHE_SETTINGS, get_ttl_hash
from celery import shared_task
from django.conf import settings
from trading.views.logger import logging
TELEGRAM_TOKEN = '5485321748:AAFDKGI1dmeibyY_gaH9LcsYFchJUwlIyAQ'
UPDATE_URL = 'https://api.telegram.org/bot' + TELEGRAM_TOKEN + '/getUpdates'
# receiver_id = '1291125688'


class Telegram:
    
    def __init__(self, userid = 0, console=True):        
        profile = getUserSocialProfile(userid,get_ttl_hash(CACHE_SETTINGS.REFRESH_CACHE_HOURLY))
        # profile = UserSocialProfile.objects.filter(user_id = userid).first()
        if profile:
            self.telegramId = profile.telegramId
        else:
            self.telegramId = 0
            
        self.userid = userid
        self.console = console

    def sendMessage(self, message, receiverid = 0, console=None):
        try:
            # if not console:
            #     console = self.console

            # if console:
            #     print(message)

            # if receiverid == 0:
            #     receiverid = self.telegramId
                
            # if receiverid > 0:
            #     if settings.HANDLE_TASKS == 'THREAD':
            #         t1 = Thread(target=send_telegram_message, args=(receiverid, message))
            #         t1.start()                    
            #     else:
            send_telegram_message(receiverid, message)
                
        except Exception as e:
            pass

    def sendMessageByUser(self, userid, message, console=None):
        # profile = UserSocialProfile.objects.filter(user_id = userid).first()
        if not console:
            console = self.console

        if console:
            print(message)

        profile = getUserSocialProfile(userid)
        if profile:
            self.sendMessage(self, message, profile.telegramId)
            
    def registerTelegramUser(self):              
        response = requests.get(UPDATE_URL)
        jsonData = json.loads(response.text)
        if jsonData.get('ok') == True:
            for data in jsonData.get('result'):
                message = data['message']['text']
                if message.split(':')[0].strip() == 'register':
                    username = message.split(':')[1].strip()
                    receiverId = data['message']['from']['id']
                    # check if user exists with the name
                    chkUser = User.objects.filter(username = username).first()
                    if chkUser:
                        profile = UserSocialProfile.objects.filter(user__username = username).first()
                        if profile:
                            profile.telegramId = receiverId
                            profile.save()
                        else:
                            profile = UserSocialProfile(
                                user = chkUser,
                                telegramId = receiverId
                            )
                            profile.save()

    # def getLoginOTP(self, brokerId, time):    
    #     IDENTIFIER = Broker.IDENTIFIER.get(brokerId)            
    #     response = requests.get(UPDATE_URL)
    #     jsonData = json.loads(response.text)        
    #     if jsonData.get('ok') == True:
    #         if len(jsonData.get('result')) > 0:
    #             data = jsonData.get('result')[-1]            
    #             receiverId = data['message']['from']['id']
    #             if receiverId == self.telegramId:
    #                 t = datetime.datetime.fromtimestamp(data['message']['date'])
    #                 if t > time:
    #                     message = data['message']['text']                        
    #                     if message.split(':')[0].strip().upper() == IDENTIFIER:
    #                         loginOTP = message.split(':')[1].strip()
    #                         return loginOTP
        
    #     return None

@shared_task(bind=True)
def send_telegram_message(self, recieverId, message):
    try:
        bot = telepot.Bot(TELEGRAM_TOKEN)
        bot.sendMessage(recieverId, message)
        if settings.LOGGING == '1':
            logging.info(message)
    except Exception as e:
        pass