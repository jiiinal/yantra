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

from threading import Thread
# from trading.views.Broker import Broker
from utils.cachesettings import get_ttl_hash, CACHE_SETTINGS
from functools import lru_cache
from celery import shared_task
from django.conf import settings
import logging
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = '5485321748:AAFDKGI1dmeibyY_gaH9LcsYFchJUwlIyAQ'
UPDATE_URL = 'https://api.telegram.org/bot' + TELEGRAM_TOKEN + '/getUpdates'
# receiver_id = '1291125688'


@lru_cache(maxsize=10)
def getUserSocialProfile(userid, TTLHash = get_ttl_hash(CACHE_SETTINGS.REFRESH_CACHE_DAILY) ):
    del TTLHash
    return UserSocialProfile.objects.filter(user_id = userid).first()

class Telegram:
    
    def __init__(self, userid = 0):        
        profile = getUserSocialProfile(userid,get_ttl_hash(CACHE_SETTINGS.REFRESH_CACHE_DAILY))
        # profile = UserSocialProfile.objects.filter(user_id = userid).first()
        if profile:
            self.telegramId = profile.telegramId
        else:
            self.telegramId = 0
            
        self.userid = userid
        self.bot = telepot.Bot(TELEGRAM_TOKEN)


    def sendMessage(self, message, receiverid = 0):
        try:
            if receiverid == 0:
                receiverid = self.telegramId
            self.bot.sendMessage(receiverid, message)
            # send_telegram_message(receiverid, message)
            logger.debug(message)
                
        except Exception as e:
            logger.info(str(e))

    def sendMessageByUser(self, userid, message):

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


@shared_task(bind=True)
def send_telegram_message(self, recieverId, message):
    try:
        bot = telepot.Bot(TELEGRAM_TOKEN)
        bot.sendMessage(recieverId, message)
        logging.info(message)
    except Exception as e:
        logging.info(str(e))