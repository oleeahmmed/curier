from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import Customer, Shipment, Bag, TrackingEvent
import json


# ==================== CUSTOMER API (for admin) ====================
@staff_member_required
def get_customer_data(request, customer_id):
    """API endpoint to fetch customer data for autofill"""
    try:
        customer = Customer.objects.get(id=customer_id)
        data = {
            'success': True,
            'name': customer.name,
            'phone': customer.phone,
            'address': customer.address,
            'country': customer.country,
        }
        return JsonResponse(data)
    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Customer not found'}, status=404)


# ==================== LOGIN/LOGOUT ====================
def login_view(request):
    """Login page"""
    if request.user.is_authenticated:
        # Redirect based on user type
        if request.user.is_staff:
            return redirect('scan_home')
        else:
            return redirect('parcel_booking')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            
            # Redirect based on user type
            if user.is_staff:
                return redirect('scan_home')
            else:
                return redirect('parcel_booking')
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'exportimport/login.html')


def logout_view(request):
    """Logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully')
    return redirect('login')


# ==================== SCAN HOME ====================
@login_required(login_url='login')
def scan_home(request):
    """Main scanning interface - Staff only"""
    # Redirect non-staff to parcel booking
    if not request.user.is_staff:
        return redirect('parcel_booking')
    
    # Get user role
    user_role = 'ADMIN'
    if hasattr(request.user, 'staff_profile'):
        user_role = request.user.staff_profile.role
    
    context = {
        'user': request.user,
        'user_role': user_role,
        'recent_scans': Shipment.objects.all().order_by('-updated_at')[:10]
    }
    return render(request, 'exportimport/scan_home.html', context)


# ==================== SCAN SHIPMENT ====================
@login_required(login_url='login')
@require_http_methods(["GET"])
def scan_shipment(request, awb):
    """Get shipment details by AWB or ID"""
    try:
        # Try to get by ID first (if awb is numeric), then by AWB number
        if awb.isdigit():
            shipment = get_object_or_404(Shipment, id=int(awb))
        else:
            shipment = get_object_or_404(Shipment, awb_number=awb)
        
        # Get next possible actions based on current status
        next_actions = get_next_actions(shipment)
        
        # Get bag and manifest info
        bag_info = None
        manifest_info = None
        
        if hasattr(shipment, 'bag') and shipment.bag:
            bag = shipment.bag
            bag_info = {
                'id': bag.id,
                'bag_number': bag.bag_number,
                'status': bag.get_status_display(),
                'weight': str(bag.weight)
            }
            
            # Get manifest info if bag is in any manifest
            manifests = bag.manifests.all()
            if manifests.exists():
                manifest = manifests.first()
                manifest_info = {
                    'id': manifest.id,
                    'manifest_number': manifest.manifest_number,
                    'flight_number': manifest.flight_number,
                    'status': manifest.get_status_display(),
                    'departure_date': manifest.departure_date.strftime('%Y-%m-%d')
                }
        
        data = {
            'success': True,
            'shipment': {
                'id': shipment.id,
                'awb_number': shipment.awb_number,
                'direction': shipment.get_direction_display(),
                'current_status': shipment.current_status,
                'status_display': shipment.get_current_status_display(),
                'customer_name': shipment.customer.name if shipment.customer else 'N/A',
                'sender_name': shipment.sender_name,
                'sender_phone': shipment.sender_phone,
                'recipient_name': shipment.recipient_name,
                'recipient_phone': shipment.recipient_phone,
                'contents': shipment.contents,
                'weight': str(shipment.weight_estimated),
                'is_fragile': shipment.is_fragile,
                'is_liquid': shipment.is_liquid,
                'is_cod': shipment.is_cod,
                'cod_amount': str(shipment.cod_amount) if shipment.cod_amount else None,
                'service_type': shipment.get_service_type_display(),
                'bag': bag_info,
                'manifest': manifest_info,
            },
            'next_actions': next_actions,
            'tracking_history': [
                {
                    'status': dict(Shipment.STATUS_CHOICES).get(event.status, event.status),
                    'description': event.description,
                    'location': event.location,
                    'timestamp': event.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                }
                for event in shipment.tracking_events.all().order_by('-timestamp')[:5]
            ]
        }
        
        return JsonResponse(data)
    
    except Shipment.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Shipment not found'
        }, status=404)


# ==================== UPDATE STATUS ====================
@login_required(login_url='login')
@require_http_methods(["POST"])
def update_shipment_status(request, shipment_id):
    """Update shipment status"""
    try:
        shipment = get_object_or_404(Shipment, id=shipment_id)
        
        data = json.loads(request.body)
        new_status = data.get('status')
        location = data.get('location', 'Unknown')
        notes = data.get('notes', '')
        
        # Validate status
        valid_statuses = [choice[0] for choice in Shipment.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'error': 'Invalid status'
            }, status=400)
        
        # Update shipment
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
            location=location,
            notes=notes,
            updated_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Status updated to {status_display}',
            'new_status': new_status,
            'status_display': status_display
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
@require_http_methods(["POST"])
def create_delivery_proof(request, shipment_id):
    """Create delivery proof"""
    try:
        from .models import DeliveryProof
        from django.core.files.base import ContentFile
        import base64
        import uuid
        
        shipment = get_object_or_404(Shipment, id=shipment_id)
        
        data = json.loads(request.body)
        receiver_name = data.get('receiver_name')
        notes = data.get('notes', '')
        signature_data = data.get('signature')  # Base64 signature
        
        if not receiver_name:
            return JsonResponse({
                'success': False,
                'error': 'Receiver name is required'
            }, status=400)
        
        # Create or update delivery proof
        delivery_proof, created = DeliveryProof.objects.get_or_create(
            shipment=shipment,
            defaults={
                'receiver_name': receiver_name,
                'notes': notes,
                'delivered_by': request.user
            }
        )
        
        if not created:
            delivery_proof.receiver_name = receiver_name
            delivery_proof.notes = notes
        
        # Save signature if provided
        if signature_data and signature_data.startswith('data:image'):
            # Extract base64 data
            format, imgstr = signature_data.split(';base64,')
            ext = format.split('/')[-1]
            
            # Generate unique filename
            filename = f'signature_{shipment.awb_number}_{uuid.uuid4().hex[:8]}.{ext}'
            
            # Save signature image
            delivery_proof.receiver_signature.save(
                filename,
                ContentFile(base64.b64decode(imgstr)),
                save=False
            )
        
        delivery_proof.save()
        
        # Update shipment status to delivered
        if shipment.direction == 'BD_TO_HK':
            shipment.current_status = 'DELIVERED_IN_HK'
        else:
            shipment.current_status = 'DELIVERED'
        shipment.save()
        
        # Create tracking event
        TrackingEvent.objects.create(
            shipment=shipment,
            status=shipment.current_status,
            description=f'Delivered to {receiver_name}',
            location='Customer Location',
            notes=notes,
            updated_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Delivery proof created successfully'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== HELPER FUNCTIONS ====================
# ==================== ALL SHIPMENTS (Staff Only) ====================
@login_required(login_url='login')
def all_shipments(request):
    """All shipments view for staff with filters"""
    # Redirect non-staff to parcel booking
    if not request.user.is_staff:
        return redirect('parcel_booking')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    customer_id = request.GET.get('customer', '')
    status = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset with related bag and manifest
    shipments = Shipment.objects.select_related('bag').prefetch_related('bag__manifests').all().order_by('-created_at')
    
    # Apply filters
    if search:
        shipments = shipments.filter(awb_number__icontains=search)
    
    if customer_id:
        shipments = shipments.filter(customer_id=customer_id)
    
    if status:
        shipments = shipments.filter(current_status=status)
    
    if date_from:
        shipments = shipments.filter(created_at__gte=date_from)
    
    if date_to:
        shipments = shipments.filter(created_at__lte=date_to)
    
    # Get all customers for filter dropdown
    customers = Customer.objects.all().order_by('name')
    
    # Get user role
    user_role = 'ADMIN'
    if hasattr(request.user, 'staff_profile'):
        user_role = request.user.staff_profile.role
    
    context = {
        'user': request.user,
        'user_role': user_role,
        'shipments': shipments,
        'customers': customers,
        'search': search,
        'selected_customer': customer_id,
        'selected_status': status,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': Shipment.STATUS_CHOICES,
    }
    return render(request, 'exportimport/shipments.html', context)


# ==================== PARCEL BOOKING (Non-Staff Users) ====================
@login_required(login_url='login')
def parcel_booking(request):
    """Parcel booking page for non-staff users"""
    # Get user's parcels only
    if request.user.is_staff:
        return redirect('scan_home')
    
    parcels = Shipment.objects.filter(booked_by=request.user).order_by('-created_at')
    
    context = {
        'user': request.user,
        'parcels': parcels,
    }
    return render(request, 'exportimport/parcel_booking.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def create_parcel(request):
    """Create new parcel - Non-staff users"""
    if request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Staff users cannot book parcels here'}, status=403)
    
    try:
        data = json.loads(request.body)
        
        # Required fields
        required_fields = [
            'direction', 'declared_value', 'weight_estimated', 'contents',
            'sender_name', 'sender_phone', 'sender_address',
            'recipient_name', 'recipient_phone', 'recipient_address'
        ]
        
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }, status=400)
        
        # Get or create customer for this user
        customer, _ = Customer.objects.get_or_create(
            user=request.user,
            defaults={
                'name': request.user.get_full_name() or request.user.username,
                'phone': data.get('sender_phone'),
                'email': request.user.email,
                'address': data.get('sender_address'),
            }
        )
        
        # Create shipment with PENDING status
        shipment = Shipment.objects.create(
            direction=data['direction'],
            customer=customer,
            declared_value=data['declared_value'],
            declared_currency=data.get('declared_currency', 'USD'),
            weight_estimated=data['weight_estimated'],
            contents=data['contents'],
            sender_name=data['sender_name'],
            sender_phone=data['sender_phone'],
            sender_address=data['sender_address'],
            sender_country=data.get('sender_country', 'Bangladesh' if data['direction'] == 'BD_TO_HK' else 'Hong Kong'),
            recipient_name=data['recipient_name'],
            recipient_phone=data['recipient_phone'],
            recipient_address=data['recipient_address'],
            recipient_country=data.get('recipient_country', 'Hong Kong' if data['direction'] == 'BD_TO_HK' else 'Bangladesh'),
            service_type=data.get('service_type', 'EXPRESS'),
            payment_method=data.get('payment_method', 'PREPAID'),
            current_status='PENDING',  # Set to PENDING
            booked_by=request.user,
            is_fragile=data.get('is_fragile', False),
            is_liquid=data.get('is_liquid', False),
            is_cod=data.get('is_cod', False),
            cod_amount=data.get('cod_amount'),
            special_instructions=data.get('special_instructions', ''),
        )
        
        # Create tracking event
        TrackingEvent.objects.create(
            shipment=shipment,
            status='PENDING',
            description='Parcel booking created',
            location='Online',
            updated_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Parcel booking created successfully',
            'parcel_id': shipment.id,
            'awb_number': shipment.awb_number
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
@require_http_methods(["GET"])
def get_parcel(request, parcel_id):
    """Get parcel details"""
    try:
        shipment = get_object_or_404(Shipment, id=parcel_id)
        
        # Check ownership for non-staff
        if not request.user.is_staff and shipment.booked_by != request.user:
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        data = {
            'success': True,
            'parcel': {
                'id': shipment.id,
                'awb_number': shipment.awb_number,
                'direction': shipment.direction,
                'direction_display': shipment.get_direction_display(),
                'current_status': shipment.current_status,
                'status_display': shipment.get_current_status_display(),
                'declared_value': str(shipment.declared_value),
                'declared_currency': shipment.declared_currency,
                'weight_estimated': str(shipment.weight_estimated),
                'contents': shipment.contents,
                'sender_name': shipment.sender_name,
                'sender_phone': shipment.sender_phone,
                'sender_address': shipment.sender_address,
                'sender_country': shipment.sender_country,
                'recipient_name': shipment.recipient_name,
                'recipient_phone': shipment.recipient_phone,
                'recipient_address': shipment.recipient_address,
                'recipient_country': shipment.recipient_country,
                'service_type': shipment.service_type,
                'payment_method': shipment.payment_method,
                'is_fragile': shipment.is_fragile,
                'is_liquid': shipment.is_liquid,
                'is_cod': shipment.is_cod,
                'cod_amount': str(shipment.cod_amount) if shipment.cod_amount else None,
                'special_instructions': shipment.special_instructions,
                'created_at': shipment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'qr_code': shipment.get_qrcode_url() if shipment.current_status == 'BOOKED' else None,
                'barcode': shipment.get_barcode_url() if shipment.current_status == 'BOOKED' else None,
            },
            'tracking_history': [
                {
                    'status': dict(Shipment.STATUS_CHOICES).get(event.status, event.status),
                    'description': event.description,
                    'location': event.location,
                    'timestamp': event.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                }
                for event in shipment.tracking_events.all().order_by('-timestamp')
            ]
        }
        
        return JsonResponse(data)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
@require_http_methods(["POST"])
def update_parcel(request, parcel_id):
    """Update parcel - Only if status is PENDING"""
    try:
        shipment = get_object_or_404(Shipment, id=parcel_id)
        
        # Check ownership for non-staff
        if not request.user.is_staff and shipment.booked_by != request.user:
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        # Only allow editing if status is PENDING
        if shipment.current_status != 'PENDING':
            return JsonResponse({
                'success': False,
                'error': 'Cannot edit parcel after it has been processed'
            }, status=400)
        
        data = json.loads(request.body)
        
        # Update fields
        shipment.direction = data.get('direction', shipment.direction)
        shipment.declared_value = data.get('declared_value', shipment.declared_value)
        shipment.declared_currency = data.get('declared_currency', shipment.declared_currency)
        shipment.weight_estimated = data.get('weight_estimated', shipment.weight_estimated)
        shipment.contents = data.get('contents', shipment.contents)
        shipment.sender_name = data.get('sender_name', shipment.sender_name)
        shipment.sender_phone = data.get('sender_phone', shipment.sender_phone)
        shipment.sender_address = data.get('sender_address', shipment.sender_address)
        shipment.recipient_name = data.get('recipient_name', shipment.recipient_name)
        shipment.recipient_phone = data.get('recipient_phone', shipment.recipient_phone)
        shipment.recipient_address = data.get('recipient_address', shipment.recipient_address)
        shipment.service_type = data.get('service_type', shipment.service_type)
        shipment.payment_method = data.get('payment_method', shipment.payment_method)
        shipment.is_fragile = data.get('is_fragile', shipment.is_fragile)
        shipment.is_liquid = data.get('is_liquid', shipment.is_liquid)
        shipment.is_cod = data.get('is_cod', shipment.is_cod)
        shipment.cod_amount = data.get('cod_amount', shipment.cod_amount)
        shipment.special_instructions = data.get('special_instructions', shipment.special_instructions)
        
        shipment.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Parcel updated successfully'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
@require_http_methods(["POST"])
def delete_parcel(request, parcel_id):
    """Delete parcel - Only if status is PENDING"""
    try:
        shipment = get_object_or_404(Shipment, id=parcel_id)
        
        # Check ownership for non-staff
        if not request.user.is_staff and shipment.booked_by != request.user:
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        # Only allow deleting if status is PENDING
        if shipment.current_status != 'PENDING':
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete parcel after it has been processed'
            }, status=400)
        
        awb = shipment.awb_number
        shipment.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Parcel {awb} deleted successfully'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== BAG MANAGEMENT (Staff Only) ====================
@login_required(login_url='login')
def bags_view(request):
    """Bag management page for staff"""
    # Redirect non-staff to parcel booking
    if not request.user.is_staff:
        return redirect('parcel_booking')
    
    bags = Bag.objects.all().order_by('-created_at')
    
    # Get stats
    total_bags = bags.count()
    open_bags = bags.filter(status='OPEN').count()
    sealed_bags = bags.filter(status='SEALED').count()
    dispatched_bags = bags.filter(status='DISPATCHED').count()
    
    # Get available shipments (BD to HK, RECEIVED_AT_BD status, no bag assigned)
    available_shipments = Shipment.objects.filter(
        direction='BD_TO_HK',
        current_status='RECEIVED_AT_BD',
        bag__isnull=True
    ).order_by('-created_at')
    
    # Get all non-delivered shipments (BD to HK, not delivered, no bag assigned)
    all_shipments = Shipment.objects.filter(
        direction='BD_TO_HK',
        bag__isnull=True
    ).exclude(
        current_status__in=['DELIVERED', 'DELIVERED_IN_HK']
    ).order_by('-created_at')
    
    context = {
        'user': request.user,
        'bags': bags,
        'total_bags': total_bags,
        'open_bags': open_bags,
        'sealed_bags': sealed_bags,
        'dispatched_bags': dispatched_bags,
        'available_shipments': available_shipments,
        'all_shipments': all_shipments,
    }
    return render(request, 'exportimport/bags.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def create_bag(request):
    """Create new bag - Staff only"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        
        bag_number = data.get('bag_number', '').strip()
        shipment_id = data.get('shipment_id')
        weight = data.get('weight', 0)
        
        if not bag_number:
            return JsonResponse({
                'success': False,
                'error': 'Bag number is required'
            }, status=400)
        
        # Check if bag number already exists
        if Bag.objects.filter(bag_number=bag_number).exists():
            return JsonResponse({
                'success': False,
                'error': 'Bag number already exists'
            }, status=400)
        
        # Create bag
        bag = Bag.objects.create(
            bag_number=bag_number,
            weight=weight,
            status='OPEN'
        )
        
        # Assign shipment if provided
        if shipment_id:
            try:
                shipment = Shipment.objects.get(id=shipment_id)
                bag.shipment = shipment
                bag.save()
                
                # Update shipment status
                shipment.current_status = 'BAGGED_FOR_EXPORT'
                shipment.save()
                
                # Create tracking event
                TrackingEvent.objects.create(
                    shipment=shipment,
                    status='BAGGED_FOR_EXPORT',
                    description=f'Added to bag {bag_number}',
                    location='Bangladesh Warehouse',
                    updated_by=request.user
                )
            except Shipment.DoesNotExist:
                pass
        
        return JsonResponse({
            'success': True,
            'message': 'Bag created successfully',
            'bag_id': bag.id
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
@require_http_methods(["GET"])
def get_bag(request, bag_id):
    """Get bag details"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        bag = get_object_or_404(Bag, id=bag_id)
        
        # Get manifest info if bag is in any manifest
        manifest_info = None
        manifests = bag.manifests.all()
        if manifests.exists():
            manifest = manifests.first()
            manifest_info = {
                'id': manifest.id,
                'manifest_number': manifest.manifest_number,
                'flight_number': manifest.flight_number,
                'status': manifest.get_status_display(),
                'departure_date': manifest.departure_date.strftime('%Y-%m-%d')
            }
        
        # Get shipment info
        shipment_info = None
        if bag.shipment:
            shipment_info = {
                'id': bag.shipment.id,
                'awb_number': bag.shipment.awb_number,
                'status': bag.shipment.get_current_status_display(),
                'recipient_name': bag.shipment.recipient_name,
                'weight': str(bag.shipment.weight_estimated)
            }
        
        # Bag model methods already handle shipment priority
        data = {
            'success': True,
            'bag': {
                'id': bag.id,
                'bag_number': bag.bag_number,
                'status': bag.status,
                'status_display': bag.get_status_display(),
                'weight': str(bag.weight),
                'shipment': bag.shipment.awb_number if bag.shipment else None,
                'shipment_info': shipment_info,
                'manifest': manifest_info,
                'created_at': bag.created_at.strftime('%Y-%m-%d %H:%M'),
                'qr_code': bag.get_qrcode_url(),  # Already prioritizes shipment AWB
                'barcode': bag.get_barcode_url(),  # Already prioritizes shipment AWB
            }
        }
        
        return JsonResponse(data)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
@require_http_methods(["POST"])
def update_bag_status(request, bag_id):
    """Update bag status - Staff only"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        bag = get_object_or_404(Bag, id=bag_id)
        data = json.loads(request.body)
        new_status = data.get('status')
        
        # Validate status
        valid_statuses = [choice[0] for choice in Bag.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'error': 'Invalid status'
            }, status=400)
        
        # Update bag status
        old_status = bag.status
        bag.status = new_status
        
        # If sealing the bag, record who sealed it
        if new_status == 'SEALED' and old_status != 'SEALED':
            bag.sealed_at = timezone.now()
            bag.sealed_by = request.user
        
        bag.save()
        
        # Update shipment status if bag has a shipment
        if bag.shipment:
            shipment = bag.shipment
            
            # Update shipment status based on bag status
            if new_status == 'SEALED':
                shipment.current_status = 'BAGGED_FOR_EXPORT'
            elif new_status == 'IN_MANIFEST':
                shipment.current_status = 'IN_EXPORT_MANIFEST'
            elif new_status == 'DISPATCHED':
                shipment.current_status = 'HANDED_TO_AIRLINE'
            
            shipment.save()
            
            # Create tracking event
            TrackingEvent.objects.create(
                shipment=shipment,
                status=shipment.current_status,
                description=f'Bag {bag.bag_number} status changed to {bag.get_status_display()}',
                location='Bangladesh Warehouse',
                updated_by=request.user
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Bag status updated to {bag.get_status_display()}',
            'new_status': new_status
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== HELPER FUNCTIONS ====================
def get_next_actions(shipment):
    """Get valid next status options"""
    current = shipment.current_status
    direction = shipment.direction
    
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
    
    # Add exception options
    next_statuses.append('EXCEPTION_DAMAGED')
    next_statuses.append('EXCEPTION_CUSTOMS_HOLD')
    
    # Return with display names
    result = []
    for status in next_statuses:
        display = dict(Shipment.STATUS_CHOICES).get(status, status)
        result.append({
            'value': status,
            'label': display,
            'is_exception': 'EXCEPTION' in status
        })
    
    return result
