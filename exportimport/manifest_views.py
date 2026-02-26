"""
Class-based views for Manifest CRUD operations
"""
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ValidationError
import json

from .models import Manifest, Bag, Shipment, TrackingEvent


class ManifestPermissionMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Mixin to check if user has manifest permissions"""
    login_url = 'login'
    
    def has_permission(self):
        # Check if user is staff - all staff members can view manifests
        if not self.request.user.is_staff:
            return False
        
        # All staff members with active staff profiles can access manifests
        if hasattr(self.request.user, 'staff_profile'):
            return self.request.user.staff_profile.is_active
        
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
        ).prefetch_related('bags').order_by('-departure_date', '-departure_time')
        
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
        ).prefetch_related('shipment')
        
        # Override manifests with the filtered queryset for count
        context['manifests'] = manifests
        
        return context


class ManifestDetailView(ManifestPermissionMixin, View):
    """Get manifest details as JSON or render HTML template"""
    template_name = 'exportimport/manifest_detail.html'
    
    def get(self, request, pk):
        try:
            manifest = get_object_or_404(
                Manifest.objects.prefetch_related('bags__shipment'),
                pk=pk
            )
            
            # Check if this is an AJAX request (wants JSON)
            # Accept header check for fetch API
            accept_header = request.headers.get('Accept', '')
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
                request.GET.get('format') == 'json' or
                'application/json' in accept_header
            )
            
            if is_ajax:
                # Return JSON response
                return self._get_json_response(manifest)
            else:
                # Render HTML template
                return render(request, self.template_name, {'manifest_id': pk})
        
        except Exception as e:
            accept_header = request.headers.get('Accept', '')
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
                request.GET.get('format') == 'json' or
                'application/json' in accept_header
            )
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
            else:
                return render(request, self.template_name, {
                    'manifest_id': pk,
                    'error': str(e)
                })
    
    def _get_json_response(self, manifest):
        """Build JSON response for AJAX requests"""
        # Get bags with shipments
        bags_data = []
        for bag in manifest.bags.all():
            # Get all shipments in this bag
            shipments = bag.shipment.all()
            shipment_info_list = []
            
            for shipment in shipments:
                shipment_info_list.append({
                    'id': shipment.id,
                    'awb_number': shipment.awb_number,
                    'recipient_name': shipment.recipient_name,
                    'recipient_phone': shipment.recipient_phone,
                    'recipient_address': shipment.recipient_address,
                    'shipper_name': shipment.shipper_name,
                    'weight': str(shipment.weight_estimated),
                    'quantity': shipment.quantity,
                    'length': str(shipment.length) if shipment.length else None,
                    'width': str(shipment.width) if shipment.width else None,
                    'height': str(shipment.height) if shipment.height else None,
                    'contents': shipment.contents,
                    'declared_value': str(shipment.declared_value),
                    'declared_currency': shipment.declared_currency,
                    'is_cod': shipment.is_cod,
                    'cod_amount': str(shipment.cod_amount) if shipment.cod_amount else None,
                    'current_status': shipment.current_status,
                    'status': shipment.get_current_status_display(),
                    'in_bag': True
                })
            
            # Get first shipment AWB for display (or None)
            first_shipment_awb = shipments.first().awb_number if shipments.exists() else None
            
            bags_data.append({
                'id': bag.id,
                'bag_number': bag.bag_number,
                'weight': str(bag.weight),
                'status': bag.status,
                'status_display': bag.get_status_display(),
                'shipment': first_shipment_awb,
                'shipment_count': shipments.count(),
                'shipment_info': shipment_info_list,
            })
        
        # Get individual shipments (not in bags)
        individual_shipments = []
        for shipment in manifest.shipments.all():
            individual_shipments.append({
                'id': shipment.id,
                'awb_number': shipment.awb_number,
                'recipient_name': shipment.recipient_name,
                'recipient_phone': shipment.recipient_phone,
                'recipient_address': shipment.recipient_address,
                'shipper_name': shipment.shipper_name,
                'weight': str(shipment.weight_estimated),
                'quantity': shipment.quantity,
                'length': str(shipment.length) if shipment.length else None,
                'width': str(shipment.width) if shipment.width else None,
                'height': str(shipment.height) if shipment.height else None,
                'contents': shipment.contents,
                'declared_value': str(shipment.declared_value),
                'declared_currency': shipment.declared_currency,
                'is_cod': shipment.is_cod,
                'cod_amount': str(shipment.cod_amount) if shipment.cod_amount else None,
                'current_status': shipment.current_status,
                'status': shipment.get_current_status_display(),
                'in_bag': False
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
                'individual_shipments': individual_shipments,
            }
        }
        
        return JsonResponse(data)


class ManifestCreateView(ManifestPermissionMixin, View):
    """Create new manifest"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['flight_number', 'departure_date', 'departure_time']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'{field.replace("_", " ").title()} is required'
                    }, status=400)
            
            # Get bag_ids and parcel_ids
            bag_ids = data.get('bag_ids', [])
            parcel_ids = data.get('parcel_ids', [])
            
            # Validate at least one bag or parcel is selected
            if not bag_ids and not parcel_ids:
                return JsonResponse({
                    'success': False,
                    'error': 'At least one bag or parcel is required'
                }, status=400)
            
            # Validate bags if provided
            if bag_ids:
                bags = Bag.objects.filter(id__in=bag_ids)
                if bags.count() != len(bag_ids):
                    return JsonResponse({
                        'success': False,
                        'error': 'One or more bags not found'
                    }, status=400)
                
                non_sealed_bags = bags.exclude(status='SEALED')
                if non_sealed_bags.exists():
                    non_sealed_numbers = ', '.join([bag.bag_number for bag in non_sealed_bags])
                    return JsonResponse({
                        'success': False,
                        'error': f'Only sealed bags can be added to manifest. Non-sealed bags: {non_sealed_numbers}'
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
            
            # Add bags if provided
            if bag_ids:
                manifest.bags.set(bags)
            
            # Add individual parcels if provided
            if parcel_ids:
                for parcel_id in parcel_ids:
                    try:
                        shipment = Shipment.objects.get(id=parcel_id)
                        manifest.add_shipment(shipment, request.user)
                    except Shipment.DoesNotExist:
                        # Skip invalid shipment IDs
                        continue
                    except ValidationError as e:
                        # If validation fails, delete the manifest and return error
                        manifest.delete()
                        return JsonResponse({
                            'success': False,
                            'error': str(e)
                        }, status=400)
            
            # Calculate totals using the model method
            manifest.calculate_totals()
            
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
                
                # Recalculate totals using the model method
                manifest.calculate_totals()
            else:
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
            # Requirements 7.1, 7.2, 7.3, 7.4: Prevent deletion of FINALIZED, DEPARTED, ARRIVED
            if manifest.status != 'DRAFT':
                status_messages = {
                    'FINALIZED': 'Cannot delete finalized manifest',
                    'DEPARTED': 'Cannot delete departed manifest',
                    'ARRIVED': 'Cannot delete arrived manifest'
                }
                error_message = status_messages.get(
                    manifest.status, 
                    f'Cannot delete manifest with status {manifest.status}'
                )
                return JsonResponse({
                    'success': False,
                    'error': error_message
                }, status=400)
            
            manifest_number = manifest.manifest_number
            
            # Requirements 7.5, 7.6: Django ManyToMany deletion only removes relationships
            # Bags and shipments are preserved when manifest is deleted
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
    """Finalize manifest using ManifestFinalizationService"""
    
    def post(self, request, pk):
        try:
            manifest = get_object_or_404(Manifest, pk=pk)
            
            # Create ManifestFinalizationService instance
            from .services import ManifestFinalizationService
            service = ManifestFinalizationService(manifest, request.user)
            
            # Call service.finalize()
            pdf_content, excel_content = service.finalize()
            
            # Generate URLs for the exports
            manifest.refresh_from_db()
            pdf_url = manifest.export.pdf_file.url if hasattr(manifest, 'export') else None
            excel_url = manifest.export.excel_file.url if hasattr(manifest, 'export') else None
            
            # Return success response with PDF and Excel URLs
            return JsonResponse({
                'success': True,
                'message': 'Manifest finalized successfully',
                'pdf_url': pdf_url,
                'excel_url': excel_url
            })
        
        except ValidationError as e:
            # Handle ValidationError and return 400
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
        
        except Exception as e:
            # Handle other exceptions and return 500
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ManifestStatusUpdateView(ManifestPermissionMixin, View):
    """Update manifest status using ManifestStatusUpdateService"""
    
    def post(self, request, pk):
        try:
            manifest = get_object_or_404(Manifest, pk=pk)
            data = json.loads(request.body)
            
            new_status = data.get('status')
            
            # Validate status
            valid_statuses = ['DEPARTED', 'IN_TRANSIT_TO_HONGKONG']
            if new_status not in valid_statuses:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid status. Valid statuses are: DEPARTED, IN_TRANSIT_TO_HONGKONG'
                }, status=400)
            
            # Validate manifest is not DRAFT
            if manifest.status == 'DRAFT':
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot update status of draft manifest'
                }, status=400)
            
            # Create ManifestStatusUpdateService instance
            from .services import ManifestStatusUpdateService
            service = ManifestStatusUpdateService(manifest, request.user)
            
            # Call service method based on requested status
            if new_status == 'DEPARTED':
                service.update_to_departed()
                message = f'Manifest status updated to DEPARTED'
            elif new_status == 'IN_TRANSIT_TO_HONGKONG':
                service.update_to_in_transit()
                message = f'Manifest shipments updated to IN_TRANSIT_TO_HK'
            
            # Return success response
            return JsonResponse({
                'success': True,
                'message': message
            })
        
        except ValidationError as e:
            # Handle ValidationError and return 400
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
        
        except Exception as e:
            # Handle other exceptions and return 500
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)



class ShipmentEditView(ManifestPermissionMixin, View):
    """Edit shipment information from manifest details page"""
    
    def post(self, request, manifest_pk, shipment_pk):
        try:
            manifest = get_object_or_404(Manifest, pk=manifest_pk)
            shipment = get_object_or_404(Shipment, pk=shipment_pk)
            
            # Validate manifest is DRAFT
            if manifest.status != 'DRAFT':
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot edit shipments in finalized manifest'
                }, status=400)
            
            # Check if shipment is in this manifest (either in a bag or as individual shipment)
            shipment_bags = shipment.bags.all()
            manifest_bags = manifest.bags.all()
            
            # Check if shipment is in a bag that's in the manifest
            is_in_bag = any(bag in manifest_bags for bag in shipment_bags)
            
            # Check if shipment is an individual shipment in the manifest
            is_individual = manifest.shipments.filter(id=shipment.id).exists()
            
            if not is_in_bag and not is_individual:
                return JsonResponse({
                    'success': False,
                    'error': 'Shipment is not in this manifest'
                }, status=400)
            
            data = json.loads(request.body)
            
            # Track if weight changed
            old_weight = shipment.weight_estimated
            weight_changed = False
            
            # Update shipment fields
            if 'weight_estimated' in data:
                new_weight = data['weight_estimated']
                if new_weight != old_weight:
                    shipment.weight_estimated = new_weight
                    weight_changed = True
            
            if 'quantity' in data:
                shipment.quantity = data['quantity']
            
            if 'length' in data:
                shipment.length = data['length']
            
            if 'width' in data:
                shipment.width = data['width']
            
            if 'height' in data:
                shipment.height = data['height']
            
            if 'payment_method' in data:
                shipment.payment_method = data['payment_method']
            
            if 'contents' in data:
                shipment.contents = data['contents']
            
            shipment.save()
            
            # Create tracking event
            TrackingEvent.objects.create(
                shipment=shipment,
                status=shipment.current_status,
                description='Shipment information updated',
                location='Bangladesh Warehouse',
                updated_by=request.user
            )
            
            # Update bag weight if weight changed and shipment is in a bag
            if weight_changed and is_in_bag:
                for bag in shipment_bags:
                    if bag in manifest_bags:
                        bag.update_weight()
                        break
            
            # Recalculate manifest totals
            manifest.calculate_totals()
            
            return JsonResponse({
                'success': True,
                'message': 'Shipment updated successfully'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ShipmentRemoveView(ManifestPermissionMixin, View):
    """Remove shipment from bag (and thus from manifest)"""
    
    def post(self, request, manifest_pk, shipment_pk):
        try:
            manifest = get_object_or_404(Manifest, pk=manifest_pk)
            shipment = get_object_or_404(Shipment, pk=shipment_pk)
            
            # Validate manifest is DRAFT
            if manifest.status != 'DRAFT':
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot remove shipments from finalized manifest'
                }, status=400)
            
            # Find bag containing shipment that is in the manifest
            shipment_bags = shipment.bags.all()
            manifest_bags = manifest.bags.all()
            
            # Find the bag that contains this shipment and is in the manifest
            bag_to_remove_from = None
            for bag in shipment_bags:
                if bag in manifest_bags:
                    bag_to_remove_from = bag
                    break
            
            if not bag_to_remove_from:
                return JsonResponse({
                    'success': False,
                    'error': 'Shipment is not in this manifest'
                }, status=400)
            
            # Store bag number for tracking event
            bag_number = bag_to_remove_from.bag_number
            
            # Remove shipment from bag
            bag_to_remove_from.shipment.remove(shipment)
            
            # Update shipment status to RECEIVED_AT_BD
            shipment.current_status = 'RECEIVED_AT_BD'
            shipment.save()
            
            # Create tracking event
            TrackingEvent.objects.create(
                shipment=shipment,
                status='RECEIVED_AT_BD',
                description=f'Removed from bag {bag_number}',
                location='Bangladesh Warehouse',
                updated_by=request.user
            )
            
            # Update bag weight
            bag_to_remove_from.update_weight()
            
            # Recalculate manifest totals
            manifest.calculate_totals()
            
            return JsonResponse({
                'success': True,
                'message': f'Shipment removed from bag {bag_number} successfully'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)



class ManifestExportPDFView(ManifestPermissionMixin, View):
    """Generate and download PDF export"""
    
    def get(self, request, pk):
        from django.http import HttpResponse
        from .services import ManifestPDFGenerator
        
        try:
            manifest = get_object_or_404(Manifest, pk=pk)
            
            # Check if manifest is FINALIZED and export exists
            if manifest.status == 'FINALIZED' and hasattr(manifest, 'export') and manifest.export.pdf_file:
                # Return stored PDF file
                pdf_file = manifest.export.pdf_file
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="MANIFEST_{manifest.manifest_number}.pdf"'
                return response
            else:
                # Generate PDF on-demand
                generator = ManifestPDFGenerator(manifest)
                pdf_content = generator.generate()
                
                response = HttpResponse(pdf_content, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="MANIFEST_{manifest.manifest_number}.pdf"'
                return response
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ManifestExportExcelView(ManifestPermissionMixin, View):
    """Generate and download Excel export"""

    def get(self, request, pk):
        from django.http import HttpResponse
        from .services import ManifestExcelGenerator

        try:
            manifest = get_object_or_404(Manifest, pk=pk)

            # Check if manifest is FINALIZED and export exists
            if manifest.status == 'FINALIZED' and hasattr(manifest, 'export') and manifest.export.excel_file:
                # Return stored Excel file
                excel_file = manifest.export.excel_file
                response = HttpResponse(excel_file.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f'attachment; filename="MANIFEST_{manifest.manifest_number}.xlsx"'
                return response
            else:
                # Generate Excel on-demand
                generator = ManifestExcelGenerator(manifest)
                excel_content = generator.generate()

                response = HttpResponse(excel_content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f'attachment; filename="MANIFEST_{manifest.manifest_number}.xlsx"'
                return response

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ManifestSearchByMAWBView(ManifestPermissionMixin, View):
    """Search for manifest by MAWB number"""
    
    def get(self, request):
        try:
            # Get MAWB parameter from query string
            mawb = request.GET.get('mawb', '').strip()
            
            if not mawb:
                return JsonResponse({
                    'success': False,
                    'error': 'MAWB number is required'
                }, status=400)
            
            # Query Manifest.objects.filter(mawb_number=mawb)
            try:
                manifest = Manifest.objects.get(mawb_number=mawb)
                
                # If found, return manifest details as JSON
                return JsonResponse({
                    'success': True,
                    'manifest': {
                        'id': manifest.id,
                        'manifest_number': manifest.manifest_number,
                        'mawb_number': manifest.mawb_number,
                        'flight_number': manifest.flight_number,
                        'status': manifest.status,
                        'departure_date': manifest.departure_date.strftime('%Y-%m-%d'),
                        'total_bags': manifest.total_bags
                    }
                })
            
            except Manifest.DoesNotExist:
                # If not found, return 404 with error message
                return JsonResponse({
                    'success': False,
                    'error': 'Manifest not found'
                }, status=404)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)




class ManifestAddShipmentView(ManifestPermissionMixin, View):
    """Add individual shipment to manifest"""
    
    def post(self, request, pk):
        try:
            manifest = get_object_or_404(Manifest, pk=pk)
            
            # Validate manifest is DRAFT
            if manifest.status != 'DRAFT':
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot add shipments to finalized manifest'
                }, status=400)
            
            data = json.loads(request.body)
            shipment_id = data.get('shipment_id')
            
            if not shipment_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Shipment ID is required'
                }, status=400)
            
            shipment = get_object_or_404(Shipment, pk=shipment_id)
            
            # Use the model method to add shipment with validation
            try:
                manifest.add_shipment(shipment, request.user)
                
                return JsonResponse({
                    'success': True,
                    'message': f'Shipment {shipment.awb_number} added to manifest successfully'
                })
            
            except ValidationError as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e),
                    'warning': True  # Flag to show as warning popup
                }, status=400)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ManifestRemoveIndividualShipmentView(ManifestPermissionMixin, View):
    """Remove individual shipment from manifest (not from bag)"""
    
    def post(self, request, pk, shipment_pk):
        try:
            manifest = get_object_or_404(Manifest, pk=pk)
            shipment = get_object_or_404(Shipment, pk=shipment_pk)
            
            # Validate manifest is DRAFT
            if manifest.status != 'DRAFT':
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot remove shipments from finalized manifest'
                }, status=400)
            
            # Check if shipment is an individual shipment (not in a bag)
            if shipment.bags.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'This shipment is in a bag. Use the bag removal function instead.'
                }, status=400)
            
            # Use the model method to remove shipment
            manifest.remove_shipment(shipment, request.user)
            
            return JsonResponse({
                'success': True,
                'message': f'Shipment {shipment.awb_number} removed from manifest successfully'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class ManifestAvailableShipmentsView(ManifestPermissionMixin, View):
    """Get available shipments that can be added to manifest"""
    
    def get(self, request, pk):
        try:
            manifest = get_object_or_404(Manifest, pk=pk)
            
            # Get shipments that are:
            # 1. Not in any bag
            # 2. Not in any manifest
            # 3. Status is BOOKED or RECEIVED_AT_BD
            # 4. Not delivered/returned/cancelled
            available_shipments = Shipment.objects.filter(
                bags__isnull=True,
                manifests__isnull=True,
                current_status__in=['BOOKED', 'RECEIVED_AT_BD']
            ).exclude(
                current_status__in=['DELIVERED', 'RETURNED', 'CANCELLED']
            ).select_related('customer').order_by('-created_at')[:50]  # Limit to 50 for performance
            
            shipments_data = []
            for shipment in available_shipments:
                shipments_data.append({
                    'id': shipment.id,
                    'awb_number': shipment.awb_number,
                    'recipient_name': shipment.recipient_name,
                    'recipient_phone': shipment.recipient_phone,
                    'weight': str(shipment.weight_estimated),
                    'contents': shipment.contents,
                    'current_status': shipment.current_status,
                    'status_display': shipment.get_current_status_display(),
                    'created_at': shipment.created_at.strftime('%Y-%m-%d %H:%M')
                })
            
            return JsonResponse({
                'success': True,
                'shipments': shipments_data
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class AvailableShipmentsForNewManifestView(ManifestPermissionMixin, View):
    """Get available shipments for creating a new manifest (no manifest ID required)"""
    
    def get(self, request):
        try:
            # Get shipments that are:
            # 1. Not in any bag
            # 2. Not in any manifest
            # 3. Status is BOOKED or RECEIVED_AT_BD
            # 4. Not delivered/returned/cancelled
            available_shipments = Shipment.objects.filter(
                bags__isnull=True,
                manifests__isnull=True,
                current_status__in=['BOOKED', 'RECEIVED_AT_BD']
            ).exclude(
                current_status__in=['DELIVERED', 'RETURNED', 'CANCELLED']
            ).select_related('customer').order_by('-created_at')[:50]  # Limit to 50 for performance
            
            shipments_data = []
            for shipment in available_shipments:
                shipments_data.append({
                    'id': shipment.id,
                    'awb_number': shipment.awb_number,
                    'recipient_name': shipment.recipient_name,
                    'recipient_phone': shipment.recipient_phone,
                    'weight': str(shipment.weight_estimated),
                    'contents': shipment.contents,
                    'current_status': shipment.current_status,
                    'status_display': shipment.get_current_status_display(),
                    'created_at': shipment.created_at.strftime('%Y-%m-%d %H:%M')
                })
            
            return JsonResponse({
                'success': True,
                'shipments': shipments_data
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
