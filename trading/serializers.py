from trading.models import (
    BrokerAccounts, JobbingSettings, Brokers, Scripts, Strategis, Exchanges, SwingSettings, SwingLog
)
from rest_framework import serializers
from django.db.models import Count
from generic_relations.relations import GenericRelatedField
from permissions.filters import permitedCompanies
from django.contrib.auth.models import User


class CreatedBySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'


class BaseCompanyModelSerializer(serializers.ModelSerializer):
    def validate(self, data):
        # if self.context.get('request').stream.method in ['PUT','PATCH']:
        # if 'created_at' in self.context.get('request').data or 'created_by' in self.context.get('request').data:
        #     raise serializers.ValidationError(f"created data not allowed in request")                
        comp = data.get('company')
        premited = permitedCompanies(self.context.get('request').user)[0]
        if comp:
            if not comp.id in premited:
                raise serializers.ValidationError(f"Not authorized for company {comp}")
        else:
            if premited == []:
                return data
        return data


class IsOwenerModelSerializer(serializers.ModelSerializer):
    # created_by = CreatedBySerializer(read_only=True)
    def validate(self, data):
        return data
        # if self.context.get('request').stream.method in ['PUT','PATCH']:
        # if 'created_at' in self.context.get('request').data or 'created_by' in self.context.get('request').data:
        #     raise serializers.ValidationError(f"created data not allowed in request")
        if self.context.get('request').user == data.get(''):
            return data
        else:
            raise serializers.ValidationError(f"Not authorized for other user {data.get('created_by')}")


class ExchangeSerializer(IsOwenerModelSerializer):
    class Meta:
        model = Exchanges
        fields = '__all__'


class BrokerSerialzer(IsOwenerModelSerializer):
    class Meta:
        model = Brokers
        fields = '__all__'


class BrokerAccountDetSerializer(IsOwenerModelSerializer):
    broker = BrokerSerialzer(read_only=True)

    class Meta:
        model = BrokerAccounts
        fields = '__all__'


class BrokerAccountSerializer(IsOwenerModelSerializer):
    class Meta:
        model = BrokerAccounts
        fields = '__all__'


class JobbingSettingDetSerializer(IsOwenerModelSerializer):
    exchange = ExchangeSerializer(read_only=True)
    target = BrokerAccountSerializer(read_only=True)

    class Meta:
        model = JobbingSettings
        fields = '__all__'


class JobbingSettingSerializer(IsOwenerModelSerializer):
    class Meta:
        model = JobbingSettings
        fields = '__all__'


class SwingSettingsDetailSerializer(IsOwenerModelSerializer):
    """Used for GET requests - includes nested objects"""
    exchange = ExchangeSerializer(read_only=True)
    target = BrokerAccountSerializer(read_only=True)

    class Meta:
        model = SwingSettings
        fields = '__all__'


class SwingSettingsWriteSerializer(IsOwenerModelSerializer):
    """Used for POST/PUT/PATCH requests - uses IDs only"""

    class Meta:
        model = SwingSettings
        fields = '__all__'
        extra_kwargs = {
            'created_by': {'read_only': True},
            'created_at': {'read_only': True},
        }


class SwingSettingsSerializer(IsOwenerModelSerializer):
    class Meta:
        model = SwingSettings
        fields = '__all__'


class SwingLogSerializer(IsOwenerModelSerializer):
    exchange_id = serializers.IntegerField(source='exchange.id', read_only=True)
    target_id = serializers.IntegerField(source='target.id', read_only=True)

    class Meta:
        model = SwingLog
        fields = '__all__'


'''
For further innovation refere below link to make single writable serializer - Limitation that target in the relationship mucst always be known.
https://github.com/LilyFoote/rest-framework-generic-relations 
'''
