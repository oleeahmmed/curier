"""
Class-based views for Manifest CRUD operations
"""
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Q
import json

from .models import Manifest, Bag, Shipment, TrackingEvent


class ManifestPermissionMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Mixin to check if user has manifest permissions"""
    login_url = 'login'
    
    def has_permission(self):
        # Check if user is staff and has appropriate role
        if not self.request.user.is_staff:
            return False
        
        # Check if user has staff profile with BD_MANAGER or ADMIN role
        if hasattr(self.request.user, 'staff_profile'):
            role = self.request.user.staff_profile.role
            return role in ['BD_MANAGER', 'ADMIN']
        
        # Superusers always have access
        return self.request.user.is_superuser


class ManifestListView(ManifestPermissionMixin, ListView):
    """List all manifests"""
    model = Manifest
    template_name = 'exportimport/manifests.html'
    context_object_name = 'manifests'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Manifest.objects.all().select_related(
            'created_by', 'finalized_by'
        ).prefetch_related('bags')
        
        # Apply filters
        search = self.request.GET.get('search', '')
        status = self.request.GET.get('status', '')
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        
        if search:
            queryset = queryset.filter(
                Q(manifest_number__icontains=search) |
                Q(flight_number__icontains=search) |
                Q(mawb_number__icontains=search)
            )
        
        if status:
            queryset = queryset.filter(status=status)
        
        if date_from:
            queryset = queryset.filter(departure_date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(departure_date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the filtered queryset
        manifests = self.get_queryset()
        
        # Add filter values
        context['search'] = self.request.GET.get('search', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        # Add stats
        context['total_manifests'] = Manifest.objects.count()
        context['draft_manifests'] = Manifest.objects.filter(status='DRAFT').count()
        context['finalized_manifests'] = Manifest.objects.filter(status='FINALIZED').count()
        context['departed_manifests'] = Manifest.objects.filter(status='DEPARTED').count()
        
        # Add available sealed bags for new manifest
        context['available_bags'] = Bag.objects.filter(
            status='SEALED',
            manifests__isnull=True
        ).select_related('shipment')
        
        # Override manifests with the filtered queryset for count
        context['manifests'] = manifests
        
        return context


class ManifestDetailView(ManifestPermissionMixin, View):
    """Get manifest details as JSON"""
    
    def get(self, request, pk):
        try:
            manifest = get_object_or_404(
                Manifest.objects.prefetch_related('bags__shipment'),
                pk=pk
            )
            
            # Get bags with shipments
            bags_data = []
            for bag in manifest.bags.all():
                shipment_info = None
                if bag.shipment:
                    shipment_info = {
                        'id': bag.shipment.id,
                        'awb_number': bag.shipment.awb_number,
                        'recipient_name': bag.shipment.recipient_name,
                        'weight': str(bag.shipment.weight_estimated),
                        'status': bag.shipment.get_current_status_display()
                    }
                
                bags_data.append({
                    'id': bag.id,
                    'bag_number': bag.bag_number,
                    'weight': str(bag.weight),
                    'status': bag.status,
                    'status_display': bag.get_status_display(),
                    'shipment': bag.shipment.awb_number if bag.shipment else None,
                    'shipment_info': shipment_info,
                })
            
            data = {
                'success': True,
                'manifest': {
                    'id': manifest.id,
                    'manifest_number': manifest.manifest_number,
                    'mawb_number': manifest.mawb_number or '',
                    'flight_number': manifest.flight_number,
                    'departure_date': manifest.departure_date.strftime('%Y-%m-%d'),
                    'departure_time': manifest.departure_time.strftime('%H:%M'),
                    'status': manifest.status,
                    'status_display': manifest.get_status_display(),
                    'airline_reference': manifest.airline_reference or '',
                    'total_bags': manifest.total_bags,
                    'total_parcels': manifest.total_parcels,
                    'total_weight': str(manifest.total_weight),
                    'created_by': manifest.created_by.get_full_name() if manifest.created_by else 'N/A',
                    'created_at': manifest.created_at.strftime('%Y-%m-%d %H:%M'),
                    'finalized_by': manifest.finalized_by.get_full_name() if manifest.finalized_by else None,
                    'finalized_at': manifest.finalized_at.strftime('%Y-%m-%d %H:%M') if manifest.finalized_at else None,
                    'bags': bags_data,
                }
            }
            
            return JsonResponse(data)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ManifestCreateView(ManifestPermissionMixin, View):
    """Create new manifest"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['flight_number', 'departure_date', 'departure_time', 'bag_ids']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'{field.replace("_", " ").title()} is required'
                    }, status=400)
            
            # Create manifest
            manifest = Manifest.objects.create(
                flight_number=data['flight_number'],
                departure_date=data['departure_date'],
                departure_time=data['departure_time'],
                mawb_number=data.get('mawb_number', ''),
                airline_reference=data.get('airline_reference', ''),
                created_by=request.user,
                status='DRAFT'
            )
            
            # Add bags
            bag_ids = data.get('bag_ids', [])
            if bag_ids:
                bags = Bag.objects.filter(id__in=bag_ids, status='SEALED')
                manifest.bags.set(bags)
                
                # Calculate totals
                total_bags = bags.count()
                total_weight = sum(bag.weight for bag in bags)
                total_parcels = bags.filter(shipment__isnull=False).count()
                
                manifest.total_bags = total_bags
                manifest.total_weight = total_weight
                manifest.total_parcels = total_parcels
                manifest.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Manifest created successfully',
                'manifest_id': manifest.id,
                'manifest_number': manifest.manifest_number
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ManifestUpdateView(ManifestPermissionMixin, View):
    """Update manifest (only if DRAFT status)"""
    
    def post(self, request, pk):
        try:
            manifest = get_object_or_404(Manifest, pk=pk)
            
            # Only allow updates if status is DRAFT
            if manifest.status != 'DRAFT':
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot update finalized manifest'
                }, status=400)
            
            data = json.loads(request.body)
            
            # Update fields
            if 'flight_number' in data:
                manifest.flight_number = data['flight_number']
            if 'departure_date' in data:
                manifest.departure_date = data['departure_date']
            if 'departure_time' in data:
                manifest.departure_time = data['departure_time']
            if 'mawb_number' in data:
                manifest.mawb_number = data['mawb_number']
            if 'airline_reference' in data:
                manifest.airline_reference = data['airline_reference']
            
            # Update bags if provided
            if 'bag_ids' in data:
                bags = Bag.objects.filter(id__in=data['bag_ids'], status='SEALED')
                manifest.bags.set(bags)
                
                # Recalculate totals
                total_bags = bags.count()
                total_weight = sum(bag.weight for bag in bags)
                total_parcels = bags.filter(shipment__isnull=False).count()
                
                manifest.total_bags = total_bags
                manifest.total_weight = total_weight
                manifest.total_parcels = total_parcels
            
            manifest.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Manifest updated successfully'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ManifestDeleteView(ManifestPermissionMixin, View):
    """Delete manifest (only if DRAFT status)"""
    
    def post(self, request, pk):
        try:
            manifest = get_object_or_404(Manifest, pk=pk)
            
            # Only allow deletion if status is DRAFT
            if manifest.status != 'DRAFT':
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot delete finalized manifest'
                }, status=400)
            
            manifest_number = manifest.manifest_number
            manifest.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Manifest {manifest_number} deleted successfully'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ManifestFinalizeView(ManifestPermissionMixin, View):
    """Finalize manifest"""
    
    def post(self, request, pk):
        try:
            manifest = get_object_or_404(Manifest, pk=pk)
            
            # Check if already finalized
            if manifest.status != 'DRAFT':
                return JsonResponse({
                    'success': False,
                    'error': 'Manifest is already finalized'
                }, status=400)
            
            # Check if manifest has bags
            if manifest.bags.count() == 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot finalize manifest without bags'
                }, status=400)
            
            # Finalize manifest
            manifest.status = 'FINALIZED'
            manifest.finalized_by = request.user
            manifest.finalized_at = timezone.now()
            manifest.save()
            
            # Update bags to IN_MANIFEST status
            for bag in manifest.bags.all():
                bag.status = 'IN_MANIFEST'
                bag.save()
                
                # Update shipment if bag has one
                if bag.shipment:
                    shipment = bag.shipment
                    shipment.current_status = 'IN_EXPORT_MANIFEST'
                    shipment.save()
                    
                    # Create tracking event
                    TrackingEvent.objects.create(
                        shipment=shipment,
                        status='IN_EXPORT_MANIFEST',
                        description=f'Added to manifest {manifest.manifest_number}',
                        location='Bangladesh Warehouse',
                        updated_by=request.user
                    )
            
            return JsonResponse({
                'success': True,
                'message': 'Manifest finalized successfully'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ManifestStatusUpdateView(ManifestPermissionMixin, View):
    """Update manifest status (DEPARTED/ARRIVED)"""
    
    def post(self, request, pk):
        try:
            manifest = get_object_or_404(Manifest, pk=pk)
            data = json.loads(request.body)
            
            new_status = data.get('status')
            
            # Validate status
            valid_statuses = ['DEPARTED', 'ARRIVED']
            if new_status not in valid_statuses:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid status'
                }, status=400)
            
            # Check if manifest is finalized
            if manifest.status == 'DRAFT':
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot update status of draft manifest'
                }, status=400)
            
            # Update status
            manifest.status = new_status
            manifest.save()
            
            # Update bags if departed
            if new_status == 'DEPARTED':
                for bag in manifest.bags.all():
                    bag.status = 'DISPATCHED'
                    bag.save()
                    
                    # Update shipment
                    if bag.shipment:
                        shipment = bag.shipment
                        shipment.current_status = 'HANDED_TO_AIRLINE'
                        shipment.save()
                        
                        TrackingEvent.objects.create(
                            shipment=shipment,
                            status='HANDED_TO_AIRLINE',
                            description=f'Departed on flight {manifest.flight_number}',
                            location='Bangladesh Airport',
                            updated_by=request.user
                        )
            
            return JsonResponse({
                'success': True,
                'message': f'Manifest status updated to {manifest.get_status_display()}'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
