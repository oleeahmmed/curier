from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import User, Group
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django import forms
from django.db import models
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import (
    Customer, Shipment, Bag, Manifest, TrackingEvent,
    DeliveryProof, ShipmentException, Location, StaffProfile, AirInvoice
)


# ==================== CUSTOM FORMS ====================



class CustomerAdminForm(forms.ModelForm):
    """Custom form to display address field as single-line input"""
    
    address = forms.CharField(
        widget=forms.TextInput(attrs={'size': '80'}),
        help_text=_('Customer address')
    )
    
    class Meta:
        model = Customer
        fields = '__all__'


# Unregister default User and Group admin
admin.site.unregister(User)
admin.site.unregister(Group)


# ==================== USER & GROUP ADMIN ====================

@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'display_groups']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'groups']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    @display(description=_("Groups"), label=True)
    def display_groups(self, obj):
        return ", ".join([group.name for group in obj.groups.all()]) or "No groups"


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    list_display = ['name', 'display_permissions_count']
    search_fields = ['name']
    filter_horizontal = ['permissions']
    
    @display(description=_("Permissions Count"))
    def display_permissions_count(self, obj):
        return obj.permissions.count()


# ==================== INLINE CLASSES ====================

class CustomerShipmentInline(TabularInline):
    model = Shipment
    extra = 0
    fields = ['awb_number', 'direction', 'recipient_name', 'current_status', 'service_type', 'payment_status', 'created_at']
    readonly_fields = ['awb_number', 'created_at']
    can_delete = False
    show_change_link = True
    verbose_name = _("Shipment")
    verbose_name_plural = _("Customer Shipments")


# Removed inline - using ManyToManyField with filter_horizontal instead


class TrackingEventInline(TabularInline):
    model = TrackingEvent
    extra = 1
    fields = ['status', 'location', 'description', 'timestamp', 'updated_by']
    readonly_fields = ['timestamp']
    can_delete = False
    show_change_link = True
    verbose_name = _("Tracking Event")
    verbose_name_plural = _("Tracking History")


# ==================== LOCATION ADMIN ====================

@admin.register(Location)
class LocationAdmin(ModelAdmin):
    list_display = ['name', 'location_type', 'city', 'country', 'is_active']
    list_filter = ['location_type', 'country', 'is_active']
    search_fields = ['name', 'city', 'country', 'address']
    list_editable = ['is_active']
    
    fieldsets = (
        (_('Location Information'), {
            'fields': (
                ('name', 'location_type', 'is_active'),
                ('country', 'city', 'phone'),
                ('address',),
            ),
            'classes': ['tab'],
        }),
    )


# ==================== STAFF PROFILE ADMIN ====================

@admin.register(StaffProfile)
class StaffProfileAdmin(ModelAdmin):
    list_display = ['user', 'role', 'location', 'employee_id', 'is_active']
    list_filter = ['role', 'location', 'is_active']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'employee_id', 'phone']
    list_editable = ['is_active']
    autocomplete_fields = ['user', 'location']
    
    fieldsets = (
        (_('Staff Information'), {
            'fields': (
                ('user', 'role', 'location'),
                ('employee_id', 'phone', 'is_active'),
            ),
            'classes': ['tab'],
        }),
    )


# ==================== CUSTOMER ADMIN ====================

@admin.register(Customer)
class CustomerAdmin(ModelAdmin):
    form = CustomerAdminForm
    list_display = ['name', 'phone', 'email', 'customer_type', 'display_user', 'created_at']
    list_filter = ['customer_type', 'created_at']
    search_fields = ['name', 'phone', 'email', 'address', 'country']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    inlines = [CustomerShipmentInline]
    
    fieldsets = (
        (_('Customer Information'), {
            'fields': (
                ('name', 'phone', 'email'),
                ('country', 'customer_type'),
                ('address',),
            ),
            'classes': ['tab'],
        }),
        (_('Additional'), {
            'fields': (
                ('user', 'created_at'),
            ),
            'classes': ['tab', 'collapse'],
        }),
    )
    
    @display(description=_("User Account"), label=True)
    def display_user(self, obj):
        if obj.user:
            return obj.user.username
        return "No account"


# ==================== SHIPMENT ADMIN ====================

@admin.register(Shipment)
class ShipmentAdmin(ModelAdmin):
    change_form_template = 'admin/exportimport/shipment_change_form.html'

    list_display = [
        'awb_number', 'direction', 'customer', 'recipient_name',
        'current_status', 'service_type', 'payment_status', 'created_at', 'book_action'
    ]

    list_filter = [
        'current_status', 'direction', 'service_type', 'payment_status',
        'payment_method', 'is_fragile', 'is_liquid', 'is_cod', 'created_at'
    ]

    search_fields = [
        'awb_number', 'external_awb', 'recipient_name', 'recipient_phone',
        'shipper_name', 'contents', 'hk_reference', 'mawb_number'
    ]

    readonly_fields = ['awb_number', 'created_at', 'updated_at', 'display_qrcode', 'display_barcode']

    autocomplete_fields = ['customer']
    actions = ['book_parcels']
    # inlines = [TrackingEventInline]

    class Media:
        js = ('admin/js/shipment_autofill.js',)
    
    @display(description=_("Actions"), label=True)
    def book_action(self, obj):
        """Display Book button for PENDING shipments"""
        if obj.current_status == 'PENDING':
            return format_html(
                '<a class="button" style="padding: 5px 10px; background-color: #417690; color: white; text-decoration: none; border-radius: 4px;" href="#">Book</a>'
            )
        return '-'
    
    def save_model(self, request, obj, form, change):
        """Override save_model to set booked_by and create TrackingEvent on status change"""
        # Track if status changed
        status_changed = False
        old_status = None
        
        if change and 'current_status' in form.changed_data:
            status_changed = True
            # Get old status from database
            old_obj = Shipment.objects.get(pk=obj.pk)
            old_status = old_obj.current_status
        
        # If status is changing to BOOKED and booked_by is not set, set it to current user
        if obj.current_status == 'BOOKED' and not obj.booked_by:
            obj.booked_by = request.user
        
        # Save the shipment (this will trigger AWB generation if needed)
        super().save_model(request, obj, form, change)
        
        # Create TrackingEvent if status changed
        if status_changed:
            TrackingEvent.objects.create(
                shipment=obj,
                status=obj.current_status,
                description=f'Status changed from {old_status} to {obj.get_current_status_display()} via admin panel',
                location='Admin Panel',
                updated_by=request.user
            )
    
    def book_parcels(self, request, queryset):
        """Admin action to book multiple pending parcels"""
        pending_parcels = queryset.filter(current_status='PENDING')
        count = 0
        
        for parcel in pending_parcels:
            parcel.current_status = 'BOOKED'
            parcel.booked_by = request.user
            parcel.save()
            
            TrackingEvent.objects.create(
                shipment=parcel,
                status='BOOKED',
                description='Parcel booked via admin panel bulk action',
                location='Admin Panel',
                updated_by=request.user
            )
            count += 1
        
        self.message_user(request, f'{count} parcel(s) booked successfully')
    
    book_parcels.short_description = 'Book selected pending parcels'
    
    @display(description=_("QR Code"))
    def display_qrcode(self, obj):
        if obj.pk:
            return format_html(
                '<img src="{}" alt="QR Code" style="max-width: 200px; border: 1px solid #ddd; padding: 10px;"/>',
                obj.get_qrcode_url()
            )
        return "Save to generate QR code"
    
    @display(description=_("Barcode"))
    def display_barcode(self, obj):
        if obj.pk:
            return format_html(
                '<img src="{}" alt="Barcode" style="max-width: 300px; border: 1px solid #ddd; padding: 10px;"/>',
                obj.get_barcode_url()
            )
        return "Save to generate barcode"

    fieldsets = (
        # ---------------- TAB 1: BASIC INFORMATION ----------------
        (_('Basic Information'), {
            'fields': (
                ('awb_number', 'direction', 'customer'),
                ('current_status','declared_value', 'weight_estimated'),
                ('contents',),
                
            ),
            'classes': ['tab'],
        }),

        # ---------------- TAB 2: SHIPPER & RECIPIENT ----------------
        (_('Shipper Information'), {
            'fields': (
                ('shipper_name', 'shipper_phone', 'shipper_country'),
                ('shipper_address',),
            ),
            'classes': ['tab'],
        }),
        
        (_('Recipient Information'), {
            'fields': (
                ('recipient_name', 'recipient_phone', 'recipient_country'),
                ('recipient_address',),
            ),
            'classes': ['tab'],
        }),

        # ---------------- TAB 3: OPTIONAL FIELDS ----------------
        (_('Optional Details'), {
            'fields': (
                ('service_type', 'payment_status'),
                ('payment_method', 'shipping_cost'),
                ('is_cod', 'cod_amount'),
                ('declared_currency',),
                ('is_liquid', 'is_fragile'),
                ('created_at', 'updated_at'),
            ),
            'classes': ['tab'],
        }),
        
        # ---------------- TAB 4: QR & BARCODE ----------------
        (_('Labels & Codes'), {
            'fields': (
                ('display_qrcode', 'display_barcode'),
            ),
            'classes': ['tab'],
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('customer', 'booked_by')



# ==================== BAG ADMIN ====================

@admin.register(Bag)
class BagAdmin(ModelAdmin):
    change_form_template = 'admin/exportimport/bag_change_form.html'
    
    list_display = ['bag_number', 'display_item_count', 'display_weight', 'status', 'created_by', 'sealed_by', 'sealed_at', 'created_at']
    list_filter = ['status', 'created_at', 'sealed_at']
    search_fields = ['bag_number', 'shipment__awb_number']
    readonly_fields = ['sealed_at', 'sealed_by', 'created_at', 'unsealed_at', 'display_qrcode', 'display_barcode']
    date_hierarchy = 'created_at'
    filter_horizontal = ('shipment',)
    
    @display(description=_("Item Count"))
    def display_item_count(self, obj):
        """Display count of shipments in the bag"""
        count = obj.get_item_count()
        return f"{count}"
    
    @display(description=_("Weight (KG)"))
    def display_weight(self, obj):
        """Display bag weight"""
        return f"{obj.weight} KG"
    
    fieldsets = (
        (_('Bag Information'), {
            'fields': (
                ('bag_number', 'status'),
                ('shipment', 'weight'),
                ('created_by', 'created_at'),
            ),
            'classes': ['tab'],
        }),
        (_('Seal Information'), {
            'fields': (
                ('sealed_by', 'sealed_at'),
            ),
            'classes': ['tab'],
        }),
        (_('Unseal Information'), {
            'fields': (
                ('unsealed_by', 'unsealed_at'),
                ('unseal_reason',),
            ),
            'classes': ['tab'],
        }),
        (_('Labels & Codes'), {
            'fields': (
                ('display_qrcode', 'display_barcode'),
            ),
            'classes': ['tab'],
        }),
    )
    
    @display(description=_("QR Code"))
    def display_qrcode(self, obj):
        if obj.pk:
            return format_html(
                '<img src="{}" alt="QR Code" style="max-width: 200px; border: 1px solid #ddd; padding: 10px;"/>',
                obj.get_qrcode_url()
            )
        return "Save to generate QR code"
    
    @display(description=_("Barcode"))
    def display_barcode(self, obj):
        if obj.pk:
            return format_html(
                '<img src="{}" alt="Barcode" style="max-width: 300px; border: 1px solid #ddd; padding: 10px;"/>',
                obj.get_barcode_url()
            )
        return "Save to generate barcode"

    def get_readonly_fields(self, request, obj=None):
        """Make bag_number readonly for existing bags"""
        readonly = list(super().get_readonly_fields(request, obj))

        # If editing existing bag, make bag_number readonly
        if obj:  # obj exists = editing existing bag
            if 'bag_number' not in readonly:
                readonly.append('bag_number')

        return readonly

    def delete_model(self, request, obj):
        """Override delete to handle validation"""
        from django.contrib import messages
        from django.core.exceptions import ValidationError

        try:
            obj.delete()
        except ValidationError as e:
            messages.error(request, str(e))




# ==================== AIR INVOICE ADMIN ====================

@admin.register(AirInvoice)
class AirInvoiceAdmin(ModelAdmin):
    list_display = ['invoice_number', 'bag', 'page_count', 'generated_at', 'generated_by', 'download_link']
    list_filter = ['generated_at']
    search_fields = ['invoice_number', 'bag__bag_number']
    readonly_fields = ['invoice_number', 'bag', 'page_count', 'generated_at', 'generated_by', 'pdf_file', 'download_link']
    date_hierarchy = 'generated_at'
    
    @display(description=_("Download PDF"), label=True)
    def download_link(self, obj):
        """Display download link for the PDF"""
        if obj.pdf_file:
            return format_html(
                '<a class="button" style="padding: 5px 10px; background-color: #417690; color: white; text-decoration: none; border-radius: 4px;" href="{}" target="_blank">Download PDF</a>',
                obj.pdf_file.url
            )
        return "No PDF available"
    
    fieldsets = (
        (_('Invoice Information'), {
            'fields': (
                ('invoice_number', 'bag'),
                ('page_count', 'pdf_file'),
            ),
            'classes': ['tab'],
        }),
        (_('Generation Details'), {
            'fields': (
                ('generated_by', 'generated_at'),
                ('download_link',),
            ),
            'classes': ['tab'],
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent manual creation of air invoices"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent manual deletion of air invoices"""
        return False


# ==================== MANIFEST ADMIN ====================

@admin.register(Manifest)
class ManifestAdmin(ModelAdmin):
    list_display = ['manifest_number', 'mawb_number', 'flight_number', 'departure_date', 'status', 'total_bags', 'total_parcels', 'total_weight']
    list_filter = ['status', 'departure_date']
    search_fields = ['manifest_number', 'mawb_number', 'flight_number', 'airline_reference']
    readonly_fields = ['manifest_number', 'created_at', 'finalized_at', 'created_by', 'finalized_by']
    date_hierarchy = 'departure_date'
    filter_horizontal = ['bags']
    
    fieldsets = (
        (_('Manifest Information'), {
            'fields': (
                ('manifest_number', 'status', 'mawb_number'),
                ('flight_number', 'departure_date', 'departure_time'),
                ('airline_reference',),
                ('bags',),
                ('total_bags', 'total_parcels', 'total_weight'),
            ),
            'classes': ['tab'],
        }),
        (_('Audit'), {
            'fields': (
                ('created_by', 'created_at'),
                ('finalized_by', 'finalized_at'),
            ),
            'classes': ['tab', 'collapse'],
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ==================== TRACKING EVENT ADMIN ====================

@admin.register(TrackingEvent)
class TrackingEventAdmin(ModelAdmin):
    list_display = ['shipment', 'status', 'location', 'timestamp', 'updated_by']
    list_filter = ['status', 'location', 'timestamp']
    search_fields = ['shipment__awb_number', 'description', 'location']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    autocomplete_fields = ['shipment']
    
    fieldsets = (
        (_('Tracking Information'), {
            'fields': (
                ('shipment', 'status', 'location'),
                ('description',),
                ('updated_by', 'timestamp'),
            ),
            'classes': ['tab'],
        }),
        (_('Additional Notes'), {
            'fields': (
                ('notes',),
            ),
            'classes': ['tab', 'collapse'],
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.updated_by:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# ==================== DELIVERY PROOF ADMIN ====================

@admin.register(DeliveryProof)
class DeliveryProofAdmin(ModelAdmin):
    list_display = ['shipment', 'receiver_name', 'delivered_by', 'delivered_at']
    list_filter = ['delivered_at']
    search_fields = ['shipment__awb_number', 'receiver_name']
    readonly_fields = ['delivered_at']
    date_hierarchy = 'delivered_at'
    autocomplete_fields = ['shipment']
    
    fieldsets = (
        (_('Delivery Information'), {
            'fields': (
                ('shipment', 'receiver_name'),
                ('delivered_by', 'delivered_at'),
                ('receiver_signature', 'delivery_photo'),
            ),
            'classes': ['tab'],
        }),
        (_('Notes'), {
            'fields': (
                ('notes',),
            ),
            'classes': ['tab', 'collapse'],
        }),
    )


# ==================== SHIPMENT EXCEPTION ADMIN ====================

@admin.register(ShipmentException)
class ShipmentExceptionAdmin(ModelAdmin):
    list_display = ['shipment', 'exception_type', 'resolution_status', 'reported_by', 'reported_at', 'resolved_at']
    list_filter = ['exception_type', 'resolution_status', 'reported_at', 'resolved_at']
    search_fields = ['shipment__awb_number', 'description', 'resolution_notes']
    readonly_fields = ['reported_at', 'resolved_at']
    date_hierarchy = 'reported_at'
    autocomplete_fields = ['shipment']
    
    fieldsets = (
        (_('Exception Information'), {
            'fields': (
                ('shipment', 'exception_type', 'claim_amount'),
                ('description',),
                ('resolution_status', 'resolved_by', 'resolved_at'),
                ('resolution_notes',),
            ),
            'classes': ['tab'],
        }),
        (_('Audit'), {
            'fields': (
                ('reported_by', 'reported_at'),
            ),
            'classes': ['tab', 'collapse'],
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.reported_by = request.user
        super().save_model(request, obj, form, change)
