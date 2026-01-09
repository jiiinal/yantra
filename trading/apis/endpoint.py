from permissions.views import (
    GenericsListCreateAPIView, GenericsRetrieveUpdateDestroyAPIView, 
    AdminListCreateAPIView, AdminRetrieveUpdateDestroyAPIView
)
from rest_framework.permissions import IsAuthenticated

from trading.models import (
    BrokerAccounts, JobbingSettings,
    Brokers, Scripts, Strategis, Exchanges
)
from trading.serializers import (
    BrokerAccountSerializer, BrokerAccountDetSerializer,
    BrokerSerialzer, JobbingSettingDetSerializer, JobbingSettingSerializer,
    ExchangeSerializer
)
from permissions.permissions import IsOwnerPermission
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from permissions.filters import IsAllowedFilterBackend

class BrokerList(GenericsListCreateAPIView):
    queryset = Brokers.objects.all()
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return BrokerSerialzer    
        return BrokerSerialzer
    # filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    # filterset_fields = ['id', 'brokerId']    
    # lookup_field = 'project'
    filter_backends = []
    permission_classes = []

class BrokerDetail(GenericsRetrieveUpdateDestroyAPIView):
    queryset = Brokers.objects.all()
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return BrokerSerialzer    
        return BrokerSerialzer
    # lookup_field = 'project'
    # filterset_fields = ['brokerId']  
    filter_backends = []
    permission_classes = []


class ExchangeList(GenericsListCreateAPIView):
    queryset = Exchanges.objects.all()
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ExchangeSerializer    
        return ExchangeSerializer
    filter_backends = []
    permission_classes = []

class ExchangeDetail(GenericsRetrieveUpdateDestroyAPIView):
    queryset = Exchanges.objects.all()
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ExchangeSerializer    
        return ExchangeSerializer
    filter_backends = []
    permission_classes = []

class BrokerAccountList(GenericsListCreateAPIView):
    queryset = BrokerAccounts.objects.all()
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return BrokerAccountDetSerializer    
        return BrokerAccountSerializer
    # filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['user_id', 'nickName','clientId','isActive']    
    # lookup_field = 'project'
    filter_backends = [IsAllowedFilterBackend]
    permission_classes = [IsAuthenticated, IsOwnerPermission]

class BrokerAccountDetail(GenericsRetrieveUpdateDestroyAPIView):
    queryset = BrokerAccounts.objects.all()
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return BrokerAccountDetSerializer    
        return BrokerAccountSerializer
    # lookup_field = 'project'
    # filter_backends = [IsAllowedFilterBackend]
    permission_classes = [IsOwnerPermission]

class JobbingSettingDetail(GenericsRetrieveUpdateDestroyAPIView):
    queryset = JobbingSettings.objects.all()
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return JobbingSettingDetSerializer    
        return JobbingSettingSerializer
    # lookup_field = 'project'
    # filter_backends = [IsAllowedFilterBackend]
    permission_classes = [IsOwnerPermission]

class JobbingSettingList(GenericsListCreateAPIView):
    queryset = JobbingSettings.objects.all()
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return JobbingSettingDetSerializer    
        return JobbingSettingSerializer
    # filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['user_id', 'exchange', 'token', 'isActive']    
    # lookup_field = 'project'
    filter_backends = [IsAllowedFilterBackend]
    permission_classes = [IsOwnerPermission]



