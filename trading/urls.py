from django.urls import path
from trading.views.jobs import testConnection, startStrategy, terminateStrategy, getSymbols, getTimeSeriesData
from trading.views.masterdata import syncSymbolsReq
from trading.apis.endpoint import ( BrokerAccountList, BrokerAccountDetail, 
                                   JobbingSettingList, JobbingSettingDetail,
                                   BrokerDetail, BrokerList,
                                   ExchangeDetail, ExchangeList
            )
from trading.Strategies.jobbing import sendTradesbyEmail

from django.http import HttpResponse as HTTPResponse

def sendMail(request):
    sendTradesbyEmail(1,'MCX','20250416')
    return HTTPResponse('Mail Sent')

urlpatterns = [
    path('symbols/sync/', syncSymbolsReq, name='symbols-sync'),
    path('symbols/', getSymbols, name='symbols'),

    path('strategy/start/', startStrategy, name='start-strategy'),
    path('strategy/terminate/',terminateStrategy, name='tearminate-strategy'),

    path('broker/', BrokerList.as_view(), name='broker'),        
    path('broker/<int:pk>/', BrokerDetail.as_view(), name='broker-pk'),

    path('exchange/', ExchangeList.as_view(), name='exchange'),            
    path('exchange/<int:pk>/', ExchangeDetail.as_view(), name='exchange-pk'),


    path('brokeraccount/test/',testConnection,name='brokeraccount-test'),
    path('data/timeseries/',getTimeSeriesData,name='data-timeseries'),
    
    path('brokeraccount/', BrokerAccountList.as_view(), name='brokeraccount-detail'),        
    path('brokeraccount/<int:pk>/', BrokerAccountDetail.as_view(), name='brokeraccount-detail-pk'),
    path('jobbingSetting/', JobbingSettingList.as_view(), name='jobbingsetting-detail'),        
    path('jobbingSetting/<int:pk>/', JobbingSettingDetail.as_view(), name='jobbingsetting-detail-pk'),

    path('sendmail/', sendMail, name='send-mail'),

]