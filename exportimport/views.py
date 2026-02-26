from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden, FileResponse, Http404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, UpdateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Customer, Shipment, Bag, TrackingEvent
from .forms import CustomerRegistrationForm, ProfileForm, PasswordChangeForm, InvoiceUploadForm
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
    
    # Get current bag context from session
    current_bag = None
    bag_id = request.session.get('current_bag_id')
    if bag_id:
        try:
            current_bag = Bag.objects.get(id=bag_id)
        except Bag.DoesNotExist:
            # Clear invalid bag from session
            request.session.pop('current_bag_id', None)
    
    # Get all customers for the create parcel form
    customers = Customer.objects.all().order_by('name')
    
    context = {
        'user': request.user,
        'user_role': user_role,
        'recent_scans': Shipment.objects.exclude(current_status='PENDING').order_by('-updated_at')[:10],
        'current_bag': current_bag,
        'customers': customers
    }
    return render(request, 'exportimport/scan_home.html', context)


# ==================== SCAN SHIPMENT ====================
@login_required(login_url='login')
@require_http_methods(["GET"])
def scan_shipment(request, awb):
    """Get shipment details by AWB or ID, or redirect to bag detail if bag number"""
    # Check if scanned code is a bag number
    if awb.startswith('BAG-'):
        # Try to find the bag
        try:
            bag = Bag.objects.get(bag_number=awb)
            # Redirect to bag detail view
            return redirect('bag_detail', bag_id=bag.id)
        except Bag.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Bag {awb} not found'
            }, status=404)
    
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
        
        # Get invoice info
        invoice_info = None
        if shipment.invoice:
            invoice_info = {
                'filename': shipment.invoice.name.split('/')[-1],
                'url': shipment.invoice.url,
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
                'shipper_name': shipment.shipper_name,
                'shipper_phone': shipment.shipper_phone,
                'recipient_name': shipment.recipient_name,
                'recipient_phone': shipment.recipient_phone,
                'contents': shipment.contents,
                'weight': str(shipment.weight_estimated),
                'quantity': shipment.quantity,
                'is_fragile': shipment.is_fragile,
                'is_liquid': shipment.is_liquid,
                'is_cod': shipment.is_cod,
                'cod_amount': str(shipment.cod_amount) if shipment.cod_amount else None,
                'service_type': shipment.get_service_type_display(),
                'bag': bag_info,
                'manifest': manifest_info,
                'invoice': invoice_info,
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
    
    # Base queryset with related bags and manifests
    shipments = Shipment.objects.prefetch_related('bags', 'bags__manifests').all().order_by('-created_at')
    
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
    """Parcel booking page for customers and staff"""
    # Staff can see all parcels, customers see only their own
    if request.user.is_staff:
        parcels = Shipment.objects.all().order_by('-created_at')
    else:
        # Customers see parcels linked to their customer profile
        if hasattr(request.user, 'customer'):
            parcels = Shipment.objects.filter(customer=request.user.customer).order_by('-created_at')
        else:
            parcels = Shipment.objects.none()
    
    # Calculate counts
    total_count = parcels.count()
    pending_count = parcels.filter(current_status='PENDING').count()
    booked_count = parcels.filter(current_status='BOOKED').count()
    in_transit_count = parcels.exclude(
        current_status__in=['PENDING', 'BOOKED', 'DELIVERED', 'DELIVERED_IN_HK']
    ).count()
    
    # Check if edit parameter is present
    edit_parcel_id = request.GET.get('edit')
    return_url = request.GET.get('return_url', '')
    
    context = {
        'user': request.user,
        'parcels': parcels,
        'total_count': total_count,
        'pending_count': pending_count,
        'booked_count': booked_count,
        'in_transit_count': in_transit_count,
        'edit_parcel_id': edit_parcel_id,
        'return_url': return_url,
    }
    return render(request, 'exportimport/parcel_booking.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def create_parcel(request):
    """Create new parcel - Both staff and non-staff users"""
    # Staff can create parcels, non-staff can only create for themselves
    
    try:
        data = json.loads(request.body)
        
        # Required fields
        required_fields = [
            'direction', 'declared_value', 'weight_estimated', 'contents',
            'shipper_name', 'shipper_phone', 'shipper_address',
            'recipient_name', 'recipient_phone', 'recipient_address'
        ]
        
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }, status=400)
        
        # For staff: allow selecting customer or creating without customer
        # For non-staff: auto-assign to their customer profile
        customer = None
        if request.user.is_staff:
            # Staff can optionally link to a customer
            customer_id = data.get('customer_id')
            if customer_id:
                try:
                    customer = Customer.objects.get(id=customer_id)
                except Customer.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Selected customer not found'
                    }, status=400)
        else:
            # Get or create customer for non-staff user
            customer, _ = Customer.objects.get_or_create(
                user=request.user,
                defaults={
                    'name': request.user.get_full_name() or request.user.username,
                    'phone': data.get('shipper_phone'),
                    'email': request.user.email,
                    'address': data.get('shipper_address'),
                }
            )
        
        # Determine initial status: staff can create as BOOKED, non-staff creates as PENDING
        initial_status = 'BOOKED' if request.user.is_staff else 'PENDING'
        
        # Create shipment
        shipment = Shipment.objects.create(
            direction=data['direction'],
            customer=customer,
            declared_value=data['declared_value'],
            declared_currency=data.get('declared_currency', 'USD'),
            weight_estimated=data['weight_estimated'],
            quantity=data.get('quantity', 1),
            contents=data['contents'],
            shipper_name=data['shipper_name'],
            shipper_phone=data['shipper_phone'],
            shipper_address=data['shipper_address'],
            shipper_country=data.get('shipper_country', 'Bangladesh' if data['direction'] == 'BD_TO_HK' else 'Hong Kong'),
            recipient_name=data['recipient_name'],
            recipient_phone=data['recipient_phone'],
            recipient_address=data['recipient_address'],
            recipient_country=data.get('recipient_country', 'Hong Kong' if data['direction'] == 'BD_TO_HK' else 'Bangladesh'),
            service_type=data.get('service_type', 'EXPRESS'),
            payment_method=data.get('payment_method', 'PREPAID'),
            current_status=initial_status,
            booked_by=request.user,
            is_fragile=data.get('is_fragile', False),
            is_liquid=data.get('is_liquid', False),
            is_cod=data.get('is_cod', False),
            cod_amount=data.get('cod_amount'),
            special_instructions=data.get('special_instructions', ''),
            length=data.get('length'),
            width=data.get('width'),
            height=data.get('height'),
        )
        
        # Create tracking event
        TrackingEvent.objects.create(
            shipment=shipment,
            status=initial_status,
            description=f'Parcel created by {"staff" if request.user.is_staff else "customer"}',
            location='Staff Dashboard' if request.user.is_staff else 'Online',
            updated_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Parcel {"booked" if request.user.is_staff else "created"} successfully',
            'parcel_id': shipment.id,
            'awb_number': shipment.awb_number,
            'status': initial_status
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
                'quantity': shipment.quantity,
                'length': str(shipment.length) if shipment.length else None,
                'width': str(shipment.width) if shipment.width else None,
                'height': str(shipment.height) if shipment.height else None,
                'contents': shipment.contents,
                'shipper_name': shipment.shipper_name,
                'shipper_phone': shipment.shipper_phone,
                'shipper_address': shipment.shipper_address,
                'shipper_country': shipment.shipper_country,
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
    """Update parcel - Staff can edit parcels in OPEN bags, customers can only edit PENDING"""
    try:
        shipment = get_object_or_404(Shipment, id=parcel_id)
        
        # Check ownership for non-staff
        if not request.user.is_staff and shipment.booked_by != request.user:
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        # Staff can edit parcels in OPEN bags or PENDING parcels
        # Customers can only edit PENDING
        if request.user.is_staff:
            # Check if parcel is in a bag
            bags = shipment.bags.all()
            if bags.exists():
                bag = bags.first()
                if bag.status != 'OPEN':
                    return JsonResponse({
                        'success': False,
                        'error': f'Cannot edit parcel in {bag.get_status_display()} bag. Unseal the bag first.'
                    }, status=400)
            # If not in a bag, allow editing for any status except delivered/exception
            elif shipment.current_status in ['DELIVERED', 'DELIVERED_IN_HK', 'EXCEPTION_DAMAGED', 'EXCEPTION_CUSTOMS_HOLD', 'RETURN_TO_SENDER']:
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot edit parcel with this status'
                }, status=400)
        else:
            # Customers can only edit PENDING
            if shipment.current_status != 'PENDING':
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot edit parcel after it has been processed'
                }, status=400)
        
        data = json.loads(request.body)
        
        # Store old weight for bag weight update
        old_weight = shipment.weight_estimated
        
        # Update fields
        shipment.direction = data.get('direction', shipment.direction)
        shipment.declared_value = data.get('declared_value', shipment.declared_value)
        shipment.declared_currency = data.get('declared_currency', shipment.declared_currency)
        shipment.weight_estimated = data.get('weight_estimated', shipment.weight_estimated)
        shipment.quantity = data.get('quantity', shipment.quantity)
        shipment.length = data.get('length', shipment.length)
        shipment.width = data.get('width', shipment.width)
        shipment.height = data.get('height', shipment.height)
        shipment.contents = data.get('contents', shipment.contents)
        shipment.shipper_name = data.get('shipper_name', shipment.shipper_name)
        shipment.shipper_phone = data.get('shipper_phone', shipment.shipper_phone)
        shipment.shipper_address = data.get('shipper_address', shipment.shipper_address)
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
        
        # Update bag weight if shipment is in a bag and weight changed
        if old_weight != shipment.weight_estimated:
            bags = shipment.bags.all()
            if bags.exists():
                bag = bags.first()
                bag.update_weight()
        
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


def book_parcel(request, parcel_id):
    """Book a pending parcel - Staff only"""
    try:
        # Fetch shipment by ID
        shipment = get_object_or_404(Shipment, id=parcel_id)

        # Validate current status is PENDING
        if shipment.current_status != 'PENDING':
            return JsonResponse({
                'success': False,
                'error': f'Cannot book parcel with status {shipment.get_current_status_display()}'
            }, status=400)

        # Validate required fields before booking
        required_fields = {
            'shipper_name': shipment.shipper_name,
            'shipper_phone': shipment.shipper_phone,
            'shipper_address': shipment.shipper_address,
            'recipient_name': shipment.recipient_name,
            'recipient_phone': shipment.recipient_phone,
            'recipient_address': shipment.recipient_address,
            'contents': shipment.contents,
            'weight_estimated': shipment.weight_estimated,
            'declared_value': shipment.declared_value
        }

        missing_fields = [field_name for field_name, field_value in required_fields.items()
                         if not field_value or (isinstance(field_value, str) and not field_value.strip())]

        if missing_fields:
            # Format field names for user-friendly display
            formatted_fields = [field.replace('_', ' ').title() for field in missing_fields]
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields',
                'missing_fields': formatted_fields
            }, status=400)

        # Change status to BOOKED and set booked_by to current user
        shipment.current_status = 'BOOKED'
        shipment.booked_by = request.user

        # Save shipment (triggers AWB generation)
        shipment.save()

        # Create TrackingEvent
        TrackingEvent.objects.create(
            shipment=shipment,
            status='BOOKED',
            description='Parcel booked by staff',
            location=request.POST.get('location', 'Staff Dashboard'),
            updated_by=request.user
        )

        # Generate HAWB URL
        from django.urls import reverse
        invoice_url = reverse('hawb_view', kwargs={'shipment_id': shipment.id})

        return JsonResponse({
            'success': True,
            'awb_number': shipment.awb_number,
            'invoice_url': invoice_url,
            'message': f'Parcel booked successfully with AWB: {shipment.awb_number}'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== PENDING PARCELS VIEW (Staff Only) ====================
@login_required(login_url='login')
@staff_member_required
def pending_parcels(request):
    """View all pending parcels - Staff only"""
    # Query all shipments with PENDING status, ordered by creation date (newest first)
    pending_shipments = Shipment.objects.filter(
        current_status='PENDING'
    ).order_by('-created_at')

    context = {
        'pending_shipments': pending_shipments,
    }

    return render(request, 'exportimport/pending_parcels.html', context)


# ==================== PARCEL DETAILS VIEW ====================
@login_required(login_url='login')
def parcel_details(request, parcel_id):
    """Display parcel details page"""
    shipment = get_object_or_404(Shipment, id=parcel_id)
    
    # Check ownership for non-staff
    if not request.user.is_staff:
        if not hasattr(request.user, 'customer') or shipment.customer != request.user.customer:
            return render(request, 'exportimport/base.html', {
                'error_message': 'You do not have permission to view this parcel'
            }, status=403)
    
    # Get tracking history
    tracking_events = shipment.tracking_events.all().order_by('-timestamp')
    
    context = {
        'shipment': shipment,
        'tracking_events': tracking_events,
        'can_edit': request.user.is_staff or shipment.current_status == 'PENDING',
        'can_book': request.user.is_staff and shipment.current_status == 'PENDING',
    }
    
    return render(request, 'exportimport/parcel_details.html', context)


# ==================== INVOICE VIEW ====================
@login_required(login_url='login')
def invoice_view(request, shipment_id):
    """Display invoice for a shipment"""
    # Fetch shipment by ID
    shipment = get_object_or_404(Shipment, id=shipment_id)
    
    # Check authorization: customer can only view own shipments, staff can view any
    if not request.user.is_staff:
        if not hasattr(request.user, 'customer') or shipment.customer != request.user.customer:
            return render(request, 'exportimport/base.html', {
                'error_message': 'You do not have permission to view this invoice'
            }, status=403)
    
    # Validate shipment status is not PENDING (return error page if PENDING)
    if shipment.current_status == 'PENDING':
        return render(request, 'exportimport/base.html', {
            'error_message': 'Invoice not available for pending shipments'
        }, status=403)
    
    # Validate shipment has AWB number (return error page if missing)
    if not shipment.awb_number:
        return render(request, 'exportimport/base.html', {
            'error_message': 'Invoice cannot be generated without AWB number'
        }, status=400)
    
    # Prepare context with shipment, barcode_url, qrcode_url, formatted_date, dimensions
    context = {
        'shipment': shipment,
        'barcode_url': shipment.get_barcode_url(),
        'qrcode_url': shipment.get_qrcode_url(),
        'formatted_date': shipment.created_at.strftime('%d/%m/%Y'),
        'dimensions': f"{shipment.length or 0}cm x {shipment.width or 0}cm x {shipment.height or 0}cm" if shipment.length else 'N/A',
        'logo_path': request.build_absolute_uri('/static/cropedlogo.png'),
    }
    
    # Render exportimport/invoice.html template
    return render(request, 'exportimport/invoice.html', context)


# ==================== COMMERCIAL INVOICE MANAGEMENT ====================
@login_required(login_url='login')
def invoice_upload_view(request, shipment_id):
    """
    Handle invoice file upload for a shipment.
    Accessible by staff and customers.
    """
    shipment = get_object_or_404(Shipment, id=shipment_id)
    
    # Check if user has access to this shipment
    if not request.user.is_staff and shipment.customer.user != request.user:
        return HttpResponseForbidden("You don't have permission to access this shipment")
    
    # Check if invoice already exists
    if shipment.invoice:
        messages.error(request, "An invoice already exists. Please delete it first.")
        return redirect('parcel_details', parcel_id=shipment_id)
    
    if request.method == 'POST':
        form = InvoiceUploadForm(request.POST, request.FILES, instance=shipment)
        if form.is_valid():
            form.save()
            messages.success(request, "Invoice uploaded successfully")
            return redirect('parcel_details', parcel_id=shipment_id)
    else:
        form = InvoiceUploadForm()
    
    return render(request, 'exportimport/invoice_upload.html', {
        'form': form,
        'shipment': shipment
    })


@login_required(login_url='login')
def invoice_delete_view(request, shipment_id):
    """
    Handle invoice deletion.
    Staff: always allowed
    Customer: only when shipment status is PENDING
    """
    shipment = get_object_or_404(Shipment, id=shipment_id)
    
    # Check if user has access to this shipment
    if not request.user.is_staff and shipment.customer.user != request.user:
        return HttpResponseForbidden("You don't have permission to access this shipment")
    
    # Check if invoice exists
    if not shipment.invoice:
        messages.error(request, "No invoice to delete")
        return redirect('parcel_details', parcel_id=shipment_id)
    
    # Permission check for customers
    if not request.user.is_staff and shipment.current_status != 'PENDING':
        messages.error(request, "You can only delete invoices for pending shipments")
        return redirect('parcel_details', parcel_id=shipment_id)
    
    if request.method == 'POST':
        # Delete the file from storage
        shipment.invoice.delete(save=False)
        shipment.invoice = None
        shipment.save()
        
        messages.success(request, "Invoice deleted successfully")
        return redirect('parcel_details', parcel_id=shipment_id)
    
    return render(request, 'exportimport/invoice_delete_confirm.html', {
        'shipment': shipment
    })


@login_required(login_url='login')
def invoice_download_view(request, shipment_id):
    """
    Serve invoice file for download.
    Staff: always allowed
    Customer: only when shipment status is BOOKED or later
    """
    shipment = get_object_or_404(Shipment, id=shipment_id)
    
    # Check if user has access to this shipment
    if not request.user.is_staff and shipment.customer.user != request.user:
        return HttpResponseForbidden("You don't have permission to access this shipment")
    
    # Check if invoice exists
    if not shipment.invoice:
        raise Http404("Invoice not found")
    
    # Permission check for customers
    if not request.user.is_staff and shipment.current_status == 'PENDING':
        return HttpResponseForbidden("Invoice not available for pending shipments")
    
    # Serve the file
    response = FileResponse(shipment.invoice.open('rb'))
    response['Content-Disposition'] = f'attachment; filename="{shipment.invoice.name}"'
    return response


@login_required(login_url='login')
def invoice_generate_view(request, shipment_id):
    """
    Generate a commercial invoice PDF for a shipment.
    Returns JSON for AJAX requests.
    """
    from .forms import InvoiceGenerationForm, ProductLineItemFormSet
    from .services import generate_invoice_pdf
    from django.core.files.base import ContentFile
    
    shipment = get_object_or_404(Shipment, id=shipment_id)
    
    # Check if user has access to this shipment
    if not request.user.is_staff and (not shipment.customer or shipment.customer.user != request.user):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        return HttpResponseForbidden("You don't have permission to access this shipment")
    
    # Check if invoice already exists
    if shipment.invoice:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'An invoice already exists. Please delete it first.'}, status=400)
        messages.error(request, "An invoice already exists. Please delete it first.")
        return redirect('parcel_details', parcel_id=shipment_id)
    
    if request.method == 'POST':
        form = InvoiceGenerationForm(shipment, request.POST)
        formset = ProductLineItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                # Extract form data
                shipper_name = form.cleaned_data['shipper_name']
                shipper_address = form.cleaned_data['shipper_address']
                consignee_name = form.cleaned_data['consignee_name']
                consignee_address = form.cleaned_data['consignee_address']
                
                # Extract line items
                line_items = []
                for item_form in formset:
                    if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE', False):
                        line_items.append({
                            'description': item_form.cleaned_data['description'],
                            'weight': item_form.cleaned_data['weight'],
                            'quantity': item_form.cleaned_data['quantity'],
                            'unit_value': item_form.cleaned_data['unit_value'],
                        })
                
                # Generate PDF
                pdf_buffer = generate_invoice_pdf(
                    shipment, shipper_name, shipper_address,
                    consignee_name, consignee_address, line_items
                )
                
                # Save to shipment
                filename = f"invoice_{shipment.awb_number}.pdf"
                shipment.invoice.save(filename, ContentFile(pdf_buffer.getvalue()), save=True)
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'Invoice generated successfully',
                        'invoice_url': shipment.invoice.url
                    })
                
                messages.success(request, "Invoice generated successfully")
                return redirect('parcel_details', parcel_id=shipment_id)
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)}, status=500)
                messages.error(request, f"Error generating invoice: {str(e)}")
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = {}
                if form.errors:
                    errors['form'] = form.errors
                if formset.errors:
                    errors['formset'] = formset.errors
                return JsonResponse({'success': False, 'errors': errors}, status=400)
    else:
        form = InvoiceGenerationForm(shipment)
        formset = ProductLineItemFormSet()
    
    # For AJAX GET requests, return form HTML
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.template.loader import render_to_string
        html = render_to_string('exportimport/invoice_generate_modal.html', {
            'form': form,
            'formset': formset,
            'shipment': shipment
        }, request=request)
        return JsonResponse({'success': True, 'html': html})
    
    return render(request, 'exportimport/invoice_generate.html', {
        'form': form,
        'formset': formset,
        'shipment': shipment
    })


# ==================== BAG MANAGEMENT (Staff Only) ====================
@login_required(login_url='login')
def bags_view(request):
    """Bag management page for staff with filters"""
    # Redirect non-staff to parcel booking
    if not request.user.is_staff:
        return redirect('parcel_booking')
    
    # Get filter parameters
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Base queryset with related data
    bags = Bag.objects.select_related('created_by', 'sealed_by').all()
    
    # Apply search filter (bag number)
    if search:
        bags = bags.filter(bag_number__icontains=search)
    
    # Apply status filter
    if status_filter:
        bags = bags.filter(status=status_filter)
    
    # Apply date range filters
    if date_from:
        bags = bags.filter(created_at__gte=date_from)
    
    if date_to:
        # Add one day to include the entire end date
        from datetime import datetime, timedelta
        try:
            end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            bags = bags.filter(created_at__lt=end_date)
        except ValueError:
            pass
    
    # Apply sorting (default: most recent first)
    valid_sort_fields = ['bag_number', '-bag_number', 'status', '-status', 
                        'weight', '-weight', 'created_at', '-created_at']
    if sort_by in valid_sort_fields:
        bags = bags.order_by(sort_by)
    else:
        bags = bags.order_by('-created_at')
    
    # Get stats (from all bags, not filtered)
    all_bags = Bag.objects.all()
    total_bags = all_bags.count()
    open_bags = all_bags.filter(status='OPEN').count()
    sealed_bags = all_bags.filter(status='SEALED').count()
    in_manifest_bags = all_bags.filter(status='IN_MANIFEST').count()
    dispatched_bags = all_bags.filter(status='DISPATCHED').count()
    
    # Get available shipments (BD to HK, RECEIVED_AT_BD status, no bag assigned)
    available_shipments = Shipment.objects.filter(
        direction='BD_TO_HK',
        current_status='RECEIVED_AT_BD',
        bags__isnull=True
    ).order_by('-created_at')
    
    # Get all non-delivered shipments (BD to HK, not delivered, no bag assigned)
    all_shipments = Shipment.objects.filter(
        direction='BD_TO_HK',
        bags__isnull=True
    ).exclude(
        current_status__in=['DELIVERED', 'DELIVERED_IN_HK']
    ).order_by('-created_at')
    
    context = {
        'user': request.user,
        'bags': bags,
        'total_bags': total_bags,
        'open_bags': open_bags,
        'sealed_bags': sealed_bags,
        'in_manifest_bags': in_manifest_bags,
        'dispatched_bags': dispatched_bags,
        'available_shipments': available_shipments,
        'all_shipments': all_shipments,
        'search': search,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'sort_by': sort_by,
        'status_choices': Bag.STATUS_CHOICES,
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
        
        shipment_ids = data.get('shipment_ids', [])
        weight = data.get('weight', 0)
        
        # Create bag (bag_number will be auto-generated by the model's save method)
        bag = Bag.objects.create(
            weight=weight,
            status='OPEN',
            created_by=request.user
        )
        
        # Assign shipments if provided
        if shipment_ids:
            for shipment_id in shipment_ids:
                try:
                    shipment = Shipment.objects.get(id=shipment_id)
                    bag.shipment.add(shipment)
                    
                    # Update shipment status
                    shipment.current_status = 'BAGGED_FOR_EXPORT'
                    shipment.save()
                    
                    # Create tracking event
                    TrackingEvent.objects.create(
                        shipment=shipment,
                        status='BAGGED_FOR_EXPORT',
                        description=f'Added to bag {bag.bag_number}',
                        location='Bangladesh Warehouse',
                        updated_by=request.user
                    )
                except Shipment.DoesNotExist:
                    pass
        
        return JsonResponse({
            'success': True,
            'message': f'Bag {bag.bag_number} created successfully',
            'bag_id': bag.id,
            'bag_number': bag.bag_number
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
def bag_detail_view(request, bag_id):
    """Display bag detail page with integrated scanner"""
    if not request.user.is_staff:
        return redirect('parcel_booking')
    
    bag = get_object_or_404(Bag, id=bag_id)
    
    # Set current bag in session for scanner context
    request.session['current_bag_id'] = bag.id
    
    # Get all shipments in the bag
    shipments = bag.shipment.all().order_by('-created_at')
    
    # Calculate total weight from shipments
    total_weight = sum(shipment.weight_estimated for shipment in shipments)
    
    # Get manifest info if bag is in any manifest
    manifest_info = None
    manifests = bag.manifests.all()
    if manifests.exists():
        manifest = manifests.first()
        manifest_info = manifest
    
    context = {
        'user': request.user,
        'bag': bag,
        'shipments': shipments,
        'item_count': bag.get_item_count(),
        'total_weight': total_weight,
        'manifest': manifest_info,
        'can_seal': bag.status == 'OPEN' and bag.get_item_count() > 0,
        'can_unseal': bag.status == 'SEALED',
        'can_add_parcels': bag.status == 'OPEN',
    }
    
    return render(request, 'exportimport/bag_detail.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def clear_bag_context(request):
    """Clear the current bag context from session"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    # Remove bag context from session
    request.session.pop('current_bag_id', None)
    
    return JsonResponse({
        'success': True,
        'message': 'Bag context cleared'
    })


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
def add_shipment_to_bag(request, bag_id):
    """Add shipment to bag - AJAX endpoint"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        bag = get_object_or_404(Bag, id=bag_id)
        data = json.loads(request.body)
        awb_number = data.get('awb_number', '').strip()
        
        if not awb_number:
            return JsonResponse({
                'success': False,
                'error': 'AWB number is required'
            }, status=400)
        
        # Find shipment by AWB
        try:
            shipment = Shipment.objects.get(awb_number=awb_number)
        except Shipment.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Shipment {awb_number} not found'
            }, status=404)
        
        # Add shipment to bag (this handles all validations)
        weight_warning = bag.add_shipment(shipment, request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Parcel {awb_number} added to bag',
            'bag_weight': str(bag.weight),
            'item_count': bag.get_item_count(),
            'weight_warning': weight_warning,
            'shipment': {
                'id': shipment.id,
                'awb_number': shipment.awb_number,
                'recipient_name': shipment.recipient_name,
                'weight': str(shipment.weight_estimated),
                'status': shipment.get_current_status_display()
            }
        })
    
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
@require_http_methods(["POST"])
def remove_shipment_from_bag(request, bag_id, shipment_id):
    """Remove shipment from bag - AJAX endpoint"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        bag = get_object_or_404(Bag, id=bag_id)
        shipment = get_object_or_404(Shipment, id=shipment_id)
        
        # Remove shipment from bag (this handles all validations)
        bag.remove_shipment(shipment, request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Parcel {shipment.awb_number} removed from bag',
            'bag_weight': str(bag.weight),
            'item_count': bag.get_item_count()
        })
    
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
@require_http_methods(["POST"])
def seal_bag_view(request, bag_id):
    """Seal bag - POST endpoint"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        bag = get_object_or_404(Bag, id=bag_id)
        
        # Seal bag (this handles all validations)
        bag.seal_bag(request.user)
        
        return JsonResponse({
            'success': True,
            'message': 'Bag sealed successfully.'
        })
    
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
@require_http_methods(["POST"])
def unseal_bag_view(request, bag_id):
    """Unseal bag - POST endpoint"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        bag = get_object_or_404(Bag, id=bag_id)
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
        
        if not reason:
            return JsonResponse({
                'success': False,
                'error': 'Reason is required to unseal bag'
            }, status=400)
        
        # Unseal bag (this handles all validations)
        bag.unseal_bag(request.user, reason)
        
        return JsonResponse({
            'success': True,
            'message': 'Bag unsealed successfully'
        })
    
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
@require_http_methods(["POST"])
def delete_bag_view(request, bag_id):
    """Delete bag - POST endpoint (only OPEN bags can be deleted)"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    try:
        bag = get_object_or_404(Bag, id=bag_id)
        bag_number = bag.bag_number
        
        # Delete bag (this handles all validations and shipment status reversion)
        bag.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Bag {bag_number} deleted successfully'
        })
    
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
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




def print_bag_label(request, bag_id):
    """Print bag label - Staff only"""
    if not request.user.is_staff:
        return redirect('parcel_booking')

    bag = get_object_or_404(Bag, id=bag_id)

    # Get item count and weight
    item_count = bag.get_item_count()

    # Get creation info with safe handling for None created_by
    if bag.created_by:
        created_by_name = bag.created_by.get_full_name() or bag.created_by.username
    else:
        created_by_name = "System"

    created_date = bag.created_at.strftime('%Y-%m-%d %H:%M')

    context = {
        'bag': bag,
        'item_count': item_count,
        'created_by_name': created_by_name,
        'created_date': created_date,
        'qr_code': bag.get_qrcode_url(),
        'barcode': bag.get_barcode_url(),
    }

    return render(request, 'exportimport/print_label.html', context)



# ==================== CUSTOMER REGISTRATION AND PROFILE ====================
class CustomerRegistrationView(CreateView):
    """
    Handles customer registration with User and Customer creation.
    """
    model = User
    form_class = CustomerRegistrationForm
    template_name = 'exportimport/register.html'
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        # Create User with hashed password
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.save()
        
        # Create Customer with OneToOne relationship
        Customer.objects.create(
            user=user,
            name=form.cleaned_data['full_name'],
            email=form.cleaned_data['email'],
            country=form.cleaned_data['country'],
            phone='',  # Empty initially, can be updated in profile
            address='',  # Empty initially, can be updated in profile
            customer_type='REGULAR'
        )
        
        messages.success(self.request, 'Registration successful! Please log in.')
        return super().form_valid(form)


class ProfileView(LoginRequiredMixin, UpdateView):
    """
    Displays and updates profile information for all users.
    For customers: updates Customer record
    For staff: updates User record only
    """
    model = Customer
    form_class = ProfileForm
    template_name = 'exportimport/profile.html'
    success_url = reverse_lazy('profile')
    login_url = '/login/'
    
    def get_object(self):
        # Return the Customer instance for the logged-in user
        # If user doesn't have a customer record (staff), create one
        try:
            return self.request.user.customer
        except Customer.DoesNotExist:
            # Create a Customer record for staff users
            return Customer.objects.create(
                user=self.request.user,
                name=self.request.user.get_full_name() or self.request.user.username,
                email=self.request.user.email or '',
                country='Bangladesh',
                phone='',
                address='',
                customer_type='REGULAR'
            )
    
    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)


class PasswordChangeView(LoginRequiredMixin, FormView):
    """
    Handles password change for authenticated customers.
    """
    form_class = PasswordChangeForm
    template_name = 'exportimport/change_password.html'
    success_url = reverse_lazy('parcel_booking')
    login_url = '/login/'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        user = self.request.user
        user.set_password(form.cleaned_data['new_password'])
        user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(self.request, user)
        
        messages.success(self.request, 'Password changed successfully!')
        return super().form_valid(form)


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


# ==================== GENERATE EMPTY HAWB ====================
@login_required(login_url='login')
@require_http_methods(["POST"])
def generate_empty_hawb(request):
    """Generate an empty HAWB for manual filling later"""
    try:
        # Only staff can generate empty HAWBs
        if not request.user.is_staff:
            return JsonResponse({
                'success': False,
                'error': 'Only staff can generate empty HAWBs'
            }, status=403)
        
        # Create empty shipment with minimal required fields
        shipment = Shipment.objects.create(
            direction=None,  # Empty direction - to be filled manually
            current_status='BOOKED',  # Set to BOOKED to generate AWB
            booked_by=request.user,
            shipper_name='',
            shipper_phone='',
            shipper_address='',
            shipper_country='',
            recipient_name='',
            recipient_phone='',
            recipient_address='',
            recipient_country='',
            contents='',
            declared_value=None,
            weight_estimated=None,
            quantity=None
        )
        
        # Create tracking event
        TrackingEvent.objects.create(
            shipment=shipment,
            status='BOOKED',
            description='Empty HAWB generated for manual filling',
            location='Bangladesh Warehouse',
            updated_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Empty HAWB generated successfully',
            'parcel_id': shipment.id,
            'awb_number': shipment.awb_number
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==================== PUBLIC TRACKING API ====================
@require_http_methods(["GET"])
def track_shipment_api(request, awb_number):
    """
    Public API endpoint to track shipment by AWB number.
    Returns only tracking events, no authentication required.
    """
    try:
        # Get shipment by AWB number
        shipment = get_object_or_404(Shipment, awb_number=awb_number)
        
        # Get tracking events
        tracking_events = shipment.tracking_events.all().order_by('-timestamp')
        
        # Format tracking events
        events = [
            {
                'status': event.status,
                'status_display': dict(Shipment.STATUS_CHOICES).get(event.status, event.status),
                'description': event.description,
                'location': event.location,
                'timestamp': event.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            }
            for event in tracking_events
        ]
        
        return JsonResponse({
            'success': True,
            'awb_number': awb_number,
            'tracking_events': events
        })
    
    except Shipment.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Shipment not found'
        }, status=404)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
