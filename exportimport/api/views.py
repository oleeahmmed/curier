from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from rest_framework_simplejwt.tokens import RefreshToken

from exportimport.models import Shipment, TrackingEvent, Bag
from .serializers import (
    ShipmentSerializer,
    ShipmentDetailSerializer,
    UpdateStatusSerializer,
    TrackingEventSerializer,
    BagSerializer,
    BagDetailSerializer,
    LoginSerializer,
    UserSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List all shipments",
        description="Get a paginated list of all shipments with basic information",
        tags=["Shipments"]
    ),
    retrieve=extend_schema(
        summary="Get shipment details",
        description="Get detailed information about a specific shipment including tracking history",
        tags=["Shipments"]
    ),
)
class ShipmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Shipment API ViewSet for scanning and tracking parcels
    """
    queryset = Shipment.objects.all()
    serializer_class = ShipmentSerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve' or self.action == 'scan':
            return ShipmentDetailSerializer
        return ShipmentSerializer
    
    @extend_schema(
        summary="Scan shipment by AWB",
        description="Scan a shipment using QR code or barcode to get full details and next possible actions",
        parameters=[
            OpenApiParameter(
                name='awb',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='AWB (Air Waybill) number from QR/Barcode scan',
                examples=[
                    OpenApiExample('BD to HK', value='DH2025112212172'),
                    OpenApiExample('HK to BD', value='HD2025112212172'),
                ]
            ),
        ],
        responses={200: ShipmentDetailSerializer},
        tags=["Scanning"]
    )
    @action(detail=False, methods=['get'], url_path='scan/(?P<awb>[^/.]+)')
    def scan(self, request, awb=None):
        """
        Scan shipment by AWB number - Main endpoint for mobile scanning
        """
        shipment = get_object_or_404(Shipment, awb_number=awb)
        serializer = self.get_serializer(shipment)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Update shipment status",
        description="Update the status of a shipment after scanning. Creates a tracking event automatically.",
        request=UpdateStatusSerializer,
        responses={200: ShipmentDetailSerializer},
        examples=[
            OpenApiExample(
                'Received at warehouse',
                value={
                    'status': 'RECEIVED_AT_BD',
                    'location': 'Dhaka Warehouse',
                    'notes': 'Parcel received in good condition'
                }
            ),
            OpenApiExample(
                'Out for delivery',
                value={
                    'status': 'OUT_FOR_DELIVERY',
                    'location': 'Dhaka City',
                    'notes': 'Assigned to driver'
                }
            ),
        ],
        tags=["Status Update"]
    )
    @action(detail=True, methods=['post'])
    def update_status(self, request, id=None):
        """
        Update shipment status - Called after user taps action button
        """
        shipment = self.get_object()
        serializer = UpdateStatusSerializer(data=request.data)
        
        if serializer.is_valid():
            new_status = serializer.validated_data['status']
            location = serializer.validated_data.get('location', '')
            notes = serializer.validated_data.get('notes', '')
            
            # Validate status is in choices
            valid_statuses = [choice[0] for choice in Shipment.STATUS_CHOICES]
            if new_status not in valid_statuses:
                return Response(
                    {'error': f'Invalid status: {new_status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update shipment status
            old_status = shipment.current_status
            shipment.current_status = new_status
            shipment.save()
            
            # Create tracking event
            status_display = dict(Shipment.STATUS_CHOICES).get(new_status, new_status)
            description = f'Status updated from {dict(Shipment.STATUS_CHOICES).get(old_status, old_status)} to {status_display}'
            
            TrackingEvent.objects.create(
                shipment=shipment,
                status=new_status,
                description=description,
                location=location or 'Unknown',
                notes=notes,
                updated_by=request.user if request.user.is_authenticated else None
            )
            
            # Return updated shipment
            response_serializer = ShipmentDetailSerializer(shipment)
            return Response({
                'success': True,
                'message': f'Status updated to {status_display}',
                'shipment': response_serializer.data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Get tracking history",
        description="Get complete tracking history for a shipment with all status changes",
        responses={200: TrackingEventSerializer(many=True)},
        tags=["Tracking"]
    )
    @action(detail=True, methods=['get'])
    def tracking(self, request, id=None):
        """
        Get tracking history for a shipment
        """
        shipment = self.get_object()
        events = shipment.tracking_events.all().order_by('-timestamp')
        serializer = TrackingEventSerializer(events, many=True)
        return Response({
            'awb_number': shipment.awb_number,
            'current_status': shipment.current_status,
            'tracking_events': serializer.data
        })



# ==================== LOGIN API ====================

@extend_schema(
    summary="Login to get JWT token",
    description="Authenticate user and get access/refresh tokens for API access",
    request=LoginSerializer,
    responses={
        200: {
            'type': 'object',
            'properties': {
                'access': {'type': 'string'},
                'refresh': {'type': 'string'},
                'user': UserSerializer,
            }
        }
    },
    examples=[
        OpenApiExample(
            'Login example',
            value={
                'username': 'staff_user',
                'password': 'password123'
            }
        ),
    ],
    tags=["Authentication"]
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login API - Get JWT tokens
    
    POST /api/auth/login/
    Body: {
        "username": "your_username",
        "password": "your_password"
    }
    
    Returns:
    - access: JWT access token (use in Authorization header)
    - refresh: JWT refresh token (to get new access token)
    - user: User profile information
    """
    serializer = LoginSerializer(data=request.data)
    
    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        
        user = authenticate(username=username, password=password)
        
        if user is not None:
            if user.is_active:
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                
                # Get user profile
                user_serializer = UserSerializer(user)
                
                return Response({
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': user_serializer.data,
                    'message': 'Login successful'
                })
            else:
                return Response(
                    {'error': 'User account is disabled'},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            return Response(
                {'error': 'Invalid username or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Get current user profile",
    description="Get authenticated user's profile information",
    responses={200: UserSerializer},
    tags=["Authentication"]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    Get current user profile
    
    GET /api/auth/profile/
    Headers: Authorization: Bearer <access_token>
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


# ==================== BAG API ====================

@extend_schema_view(
    list=extend_schema(
        summary="List all bags",
        description="Get a paginated list of all bags",
        tags=["Bags"]
    ),
    retrieve=extend_schema(
        summary="Get bag details",
        description="Get detailed information about a specific bag including shipment",
        tags=["Bags"]
    ),
)
class BagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Bag API ViewSet for scanning bags
    """
    queryset = Bag.objects.all()
    serializer_class = BagSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve' or self.action == 'scan':
            return BagDetailSerializer
        return BagSerializer
    
    @extend_schema(
        summary="Scan bag by bag number",
        description="Scan a bag using QR code or barcode to get bag and shipment details",
        parameters=[
            OpenApiParameter(
                name='bag_number',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Bag number from QR/Barcode scan',
            ),
        ],
        responses={200: BagDetailSerializer},
        tags=["Scanning"]
    )
    @action(detail=False, methods=['get'], url_path='scan/(?P<bag_number>[^/.]+)')
    def scan(self, request, bag_number=None):
        """
        Scan bag by bag number - Returns bag and shipment info
        """
        bag = get_object_or_404(Bag, bag_number=bag_number)
        serializer = self.get_serializer(bag)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Seal a bag",
        description="Mark a bag as sealed",
        request=None,
        responses={200: BagDetailSerializer},
        tags=["Bags"]
    )
    @action(detail=True, methods=['post'])
    def seal(self, request, pk=None):
        """
        Seal a bag
        
        POST /api/bags/{id}/seal/
        """
        bag = self.get_object()
        
        if bag.status == 'SEALED':
            return Response(
                {'error': 'Bag is already sealed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        bag.seal_bag(request.user)
        
        serializer = BagDetailSerializer(bag)
        return Response({
            'success': True,
            'message': 'Bag sealed successfully',
            'bag': serializer.data
        })
