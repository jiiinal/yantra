from datetime import datetime

from django.utils.timezone import make_aware
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from permissions.filters import IsAllowedFilterBackend
from permissions.permissions import IsOwnerPermission
from permissions.views import (
    GenericsListCreateAPIView, GenericsRetrieveUpdateDestroyAPIView
)
from trading.models import (
    BrokerAccounts, JobbingSettings,
    Brokers, Exchanges, SwingSettings, SwingLog
)
from trading.serializers import (
    BrokerAccountSerializer, BrokerAccountDetSerializer,
    BrokerSerialzer, JobbingSettingDetSerializer, JobbingSettingSerializer,
    ExchangeSerializer, SwingSettingsSerializer, SwingSettingsDetailSerializer, SwingLogSerializer
)


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
    filterset_fields = ['user_id', 'nickName', 'clientId', 'isActive']
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


class SwingTradingLogsList(GenericsListCreateAPIView):
    queryset = SwingLog.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return SwingSettingsSerializer
        return SwingSettingsSerializer

    # filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['user_id', 'exchange', 'token', 'isActive']
    # lookup_field = 'project'
    filter_backends = [IsAllowedFilterBackend]
    permission_classes = [IsOwnerPermission]


class SwingTradingSettingList(GenericsListCreateAPIView):
    queryset = SwingSettings.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return SwingSettingsSerializer
        return SwingSettingsSerializer

    # filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['user_id', 'exchange', 'token', 'isActive']
    # lookup_field = 'project'
    filter_backends = [IsAllowedFilterBackend]
    permission_classes = [IsOwnerPermission]


class SwingSettingDetail(GenericsRetrieveUpdateDestroyAPIView):
    queryset = SwingSettings.objects.all()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return SwingSettingsDetailSerializer
        return SwingSettingsDetailSerializer

    # lookup_field = 'project'
    # filter_backends = [IsAllowedFilterBackend]
    permission_classes = [IsOwnerPermission]


def getSwingLogs(user_id, trade_date):
    if not trade_date:
        raise ValidationError("Trade date is required")

    try:
        trade_date_obj = datetime.strptime(trade_date, "%Y%m%d").date()
    except ValueError:
        raise ValidationError("Invalid date format. Expected YYYYMMDD")

    start_dt = make_aware(datetime.combine(trade_date_obj, datetime.min.time()))
    end_dt = make_aware(datetime.combine(trade_date_obj, datetime.max.time()))

    queryset = (
        SwingLog.objects
        .filter(
            user_id=user_id,
            tradeDate__range=(start_dt, end_dt)
        )
        .order_by('-tradeDate')
    )

    return SwingLogSerializer(queryset, many=True).data


@api_view(["GET"])
def getSwingTrades(request):
    try:
        # Unified way to support both GET (query params) and POST (JSON body)
        query_params = request.query_params or request.data or request.GET

        if not query_params:
            return Response({
                'status': 'error',
                'message': 'invalid query params'
            })

        tradeDate = query_params.get('date', None)

        logs = getSwingLogs(request.user.id, tradeDate)

        return Response({
            'status': 'success',
            'message': logs.values()
        })

    except Exception as e:
        print(f"Error Jobbing Trade {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=500)
