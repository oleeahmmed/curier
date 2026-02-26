from rest_framework import serializers
from django.contrib.auth.models import User
from exportimport.models import Shipment, TrackingEvent, Bag


class ShipmentSerializer(serializers.ModelSerializer):
    """Shipment details serializer"""
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)
    status_display = serializers.CharField(source='get_current_status_display', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id',
            'awb_number',
            'direction',
            'direction_display',
            'current_status',
            'status_display',
            'customer_name',
            'shipper_name',
            'shipper_phone',
            'shipper_address',
            'shipper_country',
            'recipient_name',
            'recipient_phone',
            'recipient_address',
            'recipient_country',
            'contents',
            'weight_estimated',
            'weight_actual',
            'quantity',
            'service_type',
            'service_type_display',
            'payment_status',
            'payment_status_display',
            'is_fragile',
            'is_liquid',
            'is_cod',
            'cod_amount',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['awb_number', 'created_at', 'updated_at']


class TrackingEventSerializer(serializers.ModelSerializer):
    """Tracking event serializer"""
    
    class Meta:
        model = TrackingEvent
        fields = [
            'id',
            'status',
            'description',
            'location',
            'notes',
            'timestamp',
        ]
        read_only_fields = ['timestamp']


class ShipmentDetailSerializer(serializers.ModelSerializer):
    """Detailed shipment with tracking history"""
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)
    status_display = serializers.CharField(source='get_current_status_display', read_only=True)
    tracking_events = TrackingEventSerializer(many=True, read_only=True)
    qrcode_url = serializers.SerializerMethodField()
    barcode_url = serializers.SerializerMethodField()
    next_actions = serializers.SerializerMethodField()
    
    class Meta:
        model = Shipment
        fields = '__all__'
    
    def get_qrcode_url(self, obj):
        return obj.get_qrcode_url()
    
    def get_barcode_url(self, obj):
        return obj.get_barcode_url()
    
    def get_next_actions(self, obj):
        """Get valid next status options based on current status and direction"""
        current = obj.current_status
        direction = obj.direction
        
        # BD → HK workflow
        if direction == 'BD_TO_HK':
            actions = {
                'BOOKED': ['RECEIVED_AT_BD'],
                'RECEIVED_AT_BD': ['READY_FOR_SORTING'],
                'READY_FOR_SORTING': ['BAGGED_FOR_EXPORT'],
                'BAGGED_FOR_EXPORT': ['IN_EXPORT_MANIFEST'],
                'IN_EXPORT_MANIFEST': ['HANDED_TO_AIRLINE'],
                'HANDED_TO_AIRLINE': ['IN_TRANSIT_TO_HK'],
                'IN_TRANSIT_TO_HK': ['ARRIVED_AT_HK'],
                'ARRIVED_AT_HK': ['DELIVERED_IN_HK'],
            }
        # HK → BD workflow
        else:
            actions = {
                'BOOKED': ['IN_TRANSIT_TO_BD'],
                'IN_TRANSIT_TO_BD': ['ARRIVED_AT_BD'],
                'ARRIVED_AT_BD': ['CUSTOMS_CLEARANCE_BD'],
                'CUSTOMS_CLEARANCE_BD': ['CUSTOMS_CLEARED_BD'],
                'CUSTOMS_CLEARED_BD': ['READY_FOR_DELIVERY'],
                'READY_FOR_DELIVERY': ['OUT_FOR_DELIVERY'],
                'OUT_FOR_DELIVERY': ['DELIVERED'],
            }
        
        next_statuses = actions.get(current, [])
        
        # Add exception option for all statuses
        next_statuses.append('EXCEPTION_DAMAGED')
        next_statuses.append('EXCEPTION_CUSTOMS_HOLD')
        
        # Return with display names
        result = []
        for status in next_statuses:
            display = dict(Shipment.STATUS_CHOICES).get(status, status)
            result.append({
                'value': status,
                'label': display
            })
        
        return result


class UpdateStatusSerializer(serializers.Serializer):
    """Serializer for updating shipment status"""
    status = serializers.CharField(required=True)
    location = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class BagSerializer(serializers.ModelSerializer):
    """Bag serializer"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    shipment_awb = serializers.CharField(source='shipment.awb_number', read_only=True, allow_null=True)
    shipment_status = serializers.CharField(source='shipment.current_status', read_only=True, allow_null=True)
    
    class Meta:
        model = Bag
        fields = [
            'id',
            'bag_number',
            'shipment',
            'shipment_awb',
            'shipment_status',
            'status',
            'status_display',
            'weight',
            'sealed_at',
            'created_at',
        ]
        read_only_fields = ['sealed_at', 'created_at']


class BagDetailSerializer(serializers.ModelSerializer):
    """Detailed bag with shipment info"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    shipment_detail = ShipmentDetailSerializer(source='shipment', read_only=True)
    qrcode_url = serializers.SerializerMethodField()
    barcode_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Bag
        fields = '__all__'
    
    def get_qrcode_url(self, obj):
        return obj.get_qrcode_url()
    
    def get_barcode_url(self, obj):
        return obj.get_barcode_url()


class LoginSerializer(serializers.Serializer):
    """Login serializer"""
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class UserSerializer(serializers.ModelSerializer):
    """User profile serializer"""
    role = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'location']
    
    def get_role(self, obj):
        if hasattr(obj, 'staff_profile'):
            return obj.staff_profile.get_role_display()
        return None
    
    def get_location(self, obj):
        if hasattr(obj, 'staff_profile') and obj.staff_profile.location:
            return obj.staff_profile.location.name
        return None
