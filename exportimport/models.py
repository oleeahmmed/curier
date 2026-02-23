from django.db import models
from django.db.models import Sum, Max
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid
import qrcode
import barcode
from barcode.writer import ImageWriter
import io
import base64
import re


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    country = models.CharField(max_length=100, default='Bangladesh')
    address = models.TextField()
    customer_type = models.CharField(
        max_length=20,
        choices=[
            ('REGULAR', 'Regular'),
            ('CREDIT', 'Credit Account'),
        ],
        default='REGULAR'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.phone}"
    
    class Meta:
        ordering = ['-created_at']


class Shipment(models.Model):
    DIRECTION_CHOICES = [
        ('BD_TO_HK', 'Bangladesh to Hong Kong'),
    ]
    
    STATUS_BD_TO_HK = [
        ('PENDING', 'PENDING'),
        ('BOOKED', 'Booked'),
        ('RECEIVED_AT_BD', 'Received at Bangladesh Warehouse'),
        ('READY_FOR_SORTING', 'Ready for Sorting'),
        ('BAGGED_FOR_EXPORT', 'Bagged for Export'),
        ('IN_EXPORT_MANIFEST', 'In Export Manifest'),
        ('HANDED_TO_AIRLINE', 'Handed to Airline'),
        ('IN_TRANSIT_TO_HK', 'In Transit to Hong Kong'),
        ('ARRIVED_AT_HK', 'Arrived at Hong Kong'),
        ('DELIVERED_IN_HK', 'Delivered in Hong Kong'),
    ]
    
    STATUS_CHOICES = STATUS_BD_TO_HK + [
        ('EXCEPTION_DAMAGED', 'Exception - Damaged'),
        ('EXCEPTION_CUSTOMS_HOLD', 'Exception - Customs Hold'),
        ('RETURN_TO_SENDER', 'Return to Sender'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('REFUNDED', 'Refunded'),
    ]
    
    SERVICE_TYPE_CHOICES = [
        ('EXPRESS', 'Express'),
        ('STANDARD', 'Standard'),
    ]
    
    awb_number = models.CharField(max_length=50, unique=True, editable=False, blank=True, null=True)
    external_awb = models.CharField(max_length=50, blank=True, null=True, help_text="External AWB (from HK/Airline)")
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='shipments', null=True, blank=True)
    
    shipper_name = models.CharField(max_length=200)
    shipper_phone = models.CharField(max_length=20)
    shipper_address = models.TextField()
    shipper_country = models.CharField(max_length=100, default='Bangladesh')
    
    recipient_name = models.CharField(max_length=200)
    recipient_phone = models.CharField(max_length=20)
    recipient_address = models.TextField()
    recipient_country = models.CharField(max_length=100, default='Hong Kong')
    
    contents = models.TextField(help_text="Parcel contents")
    declared_value = models.DecimalField(max_digits=10, decimal_places=2)
    declared_currency = models.CharField(
        max_length=3,
        default='USD',
        choices=[
            ('USD', 'US Dollar'),
            ('HKD', 'Hong Kong Dollar'),
            ('BDT', 'Taka'),
        ]
    )
    
    weight_estimated = models.DecimalField(max_digits=6, decimal_places=2, help_text="KG")
    weight_actual = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="KG")
    length = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="CM")
    width = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="CM")
    height = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="CM")
    
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, default='EXPRESS')
    current_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='BOOKED')
    
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('PREPAID', 'Prepaid'),
            ('CASH', 'Cash at Warehouse'),
            ('CREDIT', 'Credit Account'),
            ('COD', 'Cash on Delivery'),
        ]
    )
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    is_cod = models.BooleanField(default=False)
    cod_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    is_fragile = models.BooleanField(default=False)
    is_liquid = models.BooleanField(default=False)
    special_instructions = models.TextField(blank=True, null=True)
    
    hk_reference = models.CharField(max_length=100, blank=True, null=True, help_text="HK warehouse reference")
    mawb_number = models.CharField(max_length=50, blank=True, null=True, help_text="Master AWB")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    booked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='booked_shipments')
    
    def save(self, *args, **kwargs):
        if not self.awb_number and self.current_status != 'PENDING':
            date_str = timezone.now().strftime('%Y%m%d')
            random_num = str(uuid.uuid4().int)[:5]
            
            if self.direction == 'BD_TO_HK':
                self.awb_number = f"DH{date_str}{random_num}"
            else:
                self.awb_number = f"HD{date_str}{random_num}"
        
        if self.direction == 'BD_TO_HK':
            self.shipper_country = 'Bangladesh'
            self.recipient_country = 'Hong Kong'
        else:
            self.shipper_country = 'Hong Kong'
            self.recipient_country = 'Bangladesh'
        
        super().save(*args, **kwargs)
    
    def get_qrcode_url(self):
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(self.awb_number)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def get_barcode_url(self):
        code128 = barcode.get_barcode_class('code128')
        barcode_instance = code128(self.awb_number, writer=ImageWriter())
        
        buffer = io.BytesIO()
        barcode_instance.write(buffer)
        buffer.seek(0)
        
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def __str__(self):
        return f"{self.awb_number} - {self.get_direction_display()}"
    
    class Meta:
        ordering = ['-created_at']


class Bag(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('SEALED', 'Sealed'),
        ('IN_MANIFEST', 'In Manifest'),
        ('DISPATCHED', 'Dispatched'),
    ]

    bag_number = models.CharField(max_length=50, unique=True)
    shipment = models.ManyToManyField('Shipment', related_name='bags', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    weight = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Bag weight in KG")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_bags', help_text="Staff who created the bag")
    created_at = models.DateTimeField(auto_now_add=True)

    sealed_at = models.DateTimeField(null=True, blank=True)
    sealed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sealed_bags')

    unsealed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='unsealed_bags', help_text="Staff who unsealed the bag")
    unsealed_at = models.DateTimeField(null=True, blank=True, help_text="When the bag was unsealed")
    unseal_reason = models.TextField(blank=True, null=True, help_text="Reason for unsealing the bag")

    def _generate_bag_number(self):
        latest_bag = Bag.objects.filter(
            bag_number__startswith='HDK-BAG-'
        ).aggregate(Max('bag_number'))
        
        latest_number = latest_bag['bag_number__max']
        
        if latest_number:
            match = re.search(r'HDK-BAG-(\d+)', latest_number)
            if match:
                next_number = int(match.group(1)) + 1
            else:
                next_number = 1
        else:
            next_number = 1
        
        return f"HDK-BAG-{next_number:06d}"

    def save(self, *args, **kwargs):
        """Override save to auto-generate bag_number if not set"""
        if not self.bag_number:
            self.bag_number = self._generate_bag_number()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Override delete to revert parcel statuses for OPEN bags"""
        if self.status != 'OPEN':
            raise ValidationError(
                f"Cannot delete bag with status {self.status}. "
                "Only OPEN bags can be deleted."
            )

        # Revert all shipments to previous status
        for shipment in self.shipment.all():
            shipment.current_status = 'RECEIVED_AT_BD'
            shipment.save()

            TrackingEvent.objects.create(
                shipment=shipment,
                status='RECEIVED_AT_BD',
                description=f"Removed from deleted bag {self.bag_number}",
                location='Bangladesh Warehouse',
                updated_by=None  # System action
            )

        super().delete(*args, **kwargs)

    def calculate_total_weight(self):
        total = self.shipment.aggregate(total_weight=Sum('weight_estimated'))['total_weight']
        return total or 0

    def update_weight(self):
        self.weight = self.calculate_total_weight()
        self.save(update_fields=['weight'])

    def get_qrcode_url(self):
        """Generate QR code for bag number"""
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(self.bag_number)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"

    def get_barcode_url(self):
        """Generate barcode for bag number"""
        code128 = barcode.get_barcode_class('code128')
        barcode_instance = code128(self.bag_number, writer=ImageWriter())

        buffer = io.BytesIO()
        barcode_instance.write(buffer)
        buffer.seek(0)

        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"

    def get_item_count(self):
        return self.shipment.count()

    def seal_bag(self, user):
        if self.shipment.count() == 0:
            raise ValidationError("Cannot seal empty bag")
        
        self.status = 'SEALED'
        self.sealed_at = timezone.now()
        self.sealed_by = user
        self.save()
        
        # Generate air invoice PDF
        from .services import generate_air_invoice_for_bag
        generate_air_invoice_for_bag(self, user)
        
        for shipment in self.shipment.all():
            TrackingEvent.objects.create(
                shipment=shipment,
                status='BAGGED_FOR_EXPORT',
                description=f"Bag {self.bag_number} sealed",
                location='Bangladesh Warehouse',
                updated_by=user
            )
    
    def unseal_bag(self, user, reason):
        if self.status in ['IN_MANIFEST', 'DISPATCHED']:
            raise ValidationError(
                "Cannot unseal bag that is in manifest or dispatched"
            )
        
        if self.status != 'SEALED':
            raise ValidationError(
                f"Can only unseal SEALED bags (current status: {self.status})"
            )
        
        if not reason or not reason.strip():
            raise ValidationError("Reason is required to unseal bag")
        
        self.status = 'OPEN'
        self.unsealed_by = user
        self.unsealed_at = timezone.now()
        self.unseal_reason = reason
        self.save()
        
        if hasattr(self, 'air_invoice') and self.air_invoice:
            if self.air_invoice.pdf_file:
                self.air_invoice.pdf_file.delete(save=False)
            self.air_invoice.delete()
        
        for shipment in self.shipment.all():
            TrackingEvent.objects.create(
                shipment=shipment,
                status='BAGGED_FOR_EXPORT',
                description=f"Bag {self.bag_number} unsealed - Reason: {reason}",
                location='Bangladesh Warehouse',
                updated_by=user
            )

    def add_shipment(self, shipment, user):
        if shipment.current_status not in ['BOOKED', 'RECEIVED_AT_BD']:
            raise ValidationError(
                f"Parcel {shipment.awb_number} cannot be added. "
                f"Status must be BOOKED or RECEIVED_AT_BD (current: {shipment.current_status})"
            )

        existing_bags = shipment.bags.all()
        if existing_bags.exists():
            existing_bag = existing_bags.first()
            raise ValidationError(
                f"Parcel {shipment.awb_number} is already in {existing_bag.bag_number}"
            )

        new_weight = self.weight + shipment.weight_estimated
        weight_warning = None
        if hasattr(self, 'max_weight') and self.max_weight and new_weight > self.max_weight:
            weight_warning = (
                f"Adding this parcel will exceed bag weight limit "
                f"({self.weight} + {shipment.weight_estimated} > {self.max_weight} KG). Continue?"
            )

        self.shipment.add(shipment)

        shipment.current_status = 'BAGGED_FOR_EXPORT'
        shipment.save()

        self.weight = new_weight
        self.save()

        TrackingEvent.objects.create(
            shipment=shipment,
            status='BAGGED_FOR_EXPORT',
            description=f"Added to {self.bag_number}",
            location='Bangladesh Warehouse',
            updated_by=user
        )

        return weight_warning

    def remove_shipment(self, shipment, user):
        if self.status != 'OPEN':
            raise ValidationError(
                f"Cannot modify sealed bag. Unseal first if needed."
            )
        
        if not self.shipment.filter(id=shipment.id).exists():
            raise ValidationError(
                f"Parcel {shipment.awb_number} is not in this bag"
            )
        
        previous_status = 'RECEIVED_AT_BD'
        
        self.shipment.remove(shipment)
        
        shipment.current_status = previous_status
        shipment.save()
        
        self.weight -= shipment.weight_estimated
        if self.weight < 0:
            self.weight = 0
        self.save()
        
        TrackingEvent.objects.create(
            shipment=shipment,
            status=previous_status,
            description=f"Removed from {self.bag_number}",
            location='Bangladesh Warehouse',
            updated_by=user
        )
    
    def get_item_count(self):
        """Get the number of shipments in this bag"""
        return self.shipment.count()

    def __str__(self):
        return f"{self.bag_number}"

    class Meta:
        ordering = ['-created_at']


class AirInvoice(models.Model):
    bag = models.OneToOneField(Bag, on_delete=models.CASCADE, related_name='air_invoice')
    invoice_number = models.CharField(max_length=50, unique=True)
    pdf_file = models.FileField(upload_to='air_invoices/')
    page_count = models.IntegerField(help_text="Number of pages in PDF (equals number of parcels)")
    
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"Invoice {self.invoice_number} for {self.bag.bag_number}"
    
    class Meta:
        verbose_name = 'Air Invoice'
        verbose_name_plural = 'Air Invoices'
        ordering = ['-generated_at']


class Manifest(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('FINALIZED', 'Finalized'),
        ('DEPARTED', 'Departed from Bangladesh'),
        ('ARRIVED', 'Arrived in Hong Kong'),
    ]
    
    manifest_number = models.CharField(max_length=50, unique=True, editable=False)
    mawb_number = models.CharField(max_length=50, blank=True, null=True, help_text="Master AWB from airline")
    
    flight_number = models.CharField(max_length=20)
    departure_date = models.DateField()
    departure_time = models.TimeField()
    
    bags = models.ManyToManyField(Bag, related_name='manifests')
    
    total_bags = models.IntegerField(default=0)
    total_parcels = models.IntegerField(default=0)
    total_weight = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    airline_reference = models.CharField(max_length=100, blank=True, null=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_manifests')
    finalized_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='finalized_manifests')
    created_at = models.DateTimeField(auto_now_add=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.manifest_number:
            date_str = timezone.now().strftime('%Y%m%d')
            random_num = str(uuid.uuid4().int)[:4]
            self.manifest_number = f"MF{date_str}{random_num}"
        super().save(*args, **kwargs)
    
    def calculate_totals(self):
        self.total_bags = self.bags.count()
        
        total_parcels = 0
        for bag in self.bags.all():
            total_parcels += bag.shipment.count()
        self.total_parcels = total_parcels
        
        weight_sum = self.bags.aggregate(total=Sum('weight'))['total']
        self.total_weight = weight_sum if weight_sum is not None else 0
        
        self.save(update_fields=['total_bags', 'total_parcels', 'total_weight'])
    
    def finalize_manifest(self, user):
        self.status = 'FINALIZED'
        self.finalized_by = user
        self.finalized_at = timezone.now()
        
        for bag in self.bags.all():
            bag.status = 'IN_MANIFEST'
            bag.save()
            
            for shipment in bag.shipments.all():
                shipment.current_status = 'IN_EXPORT_MANIFEST'
                shipment.save()
                
                TrackingEvent.objects.create(
                    shipment=shipment,
                    status='IN_EXPORT_MANIFEST',
                    description='Added to export manifest',
                    location='Bangladesh Warehouse'
                )
        
        self.save()

    
    def __str__(self):
        return f"{self.manifest_number} - {self.flight_number}"
    
    class Meta:
        ordering = ['-departure_date', '-departure_time']


class ManifestExport(models.Model):
    """
    Store generated PDF and Excel exports for finalized manifests.
    """
    manifest = models.OneToOneField(
        Manifest, 
        on_delete=models.CASCADE, 
        related_name='export'
    )
    
    pdf_file = models.FileField(
        upload_to='manifest_exports/pdf/',
        help_text="Generated PDF export"
    )
    
    excel_file = models.FileField(
        upload_to='manifest_exports/excel/',
        help_text="Generated Excel export"
    )
    
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True
    )
    
    def __str__(self):
        return f"Export for {self.manifest.manifest_number}"
    
    class Meta:
        verbose_name = 'Manifest Export'
        verbose_name_plural = 'Manifest Exports'
        ordering = ['-generated_at']


class TrackingEvent(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_events')
    status = models.CharField(max_length=50)
    description = models.TextField()
    location = models.CharField(max_length=100)
    
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.shipment.awb_number} - {self.status}"
    
    class Meta:
        ordering = ['-timestamp']


class DeliveryProof(models.Model):
    shipment = models.OneToOneField(Shipment, on_delete=models.CASCADE, related_name='delivery_proof')
    
    receiver_name = models.CharField(max_length=200)
    receiver_signature = models.ImageField(upload_to='signatures/', null=True, blank=True)
    delivery_photo = models.ImageField(upload_to='delivery_photos/', null=True, blank=True)
    
    delivered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='delivered_shipments')
    delivered_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"POD for {self.shipment.awb_number}"


class ShipmentException(models.Model):
    EXCEPTION_TYPES = [
        ('DAMAGED', 'Damaged'),
        ('CUSTOMS_HOLD', 'Customs Hold'),
        ('ADDRESS_ISSUE', 'Address Issue'),
        ('RECIPIENT_UNAVAILABLE', 'Recipient Unavailable'),
        ('WEIGHT_DISCREPANCY', 'Weight Discrepancy'),
        ('PROHIBITED_ITEM', 'Prohibited Item'),
        ('OTHER', 'Other'),
    ]
    
    RESOLUTION_STATUS = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]
    
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='exceptions')
    exception_type = models.CharField(max_length=30, choices=EXCEPTION_TYPES)
    description = models.TextField()
    
    resolution_status = models.CharField(max_length=20, choices=RESOLUTION_STATUS, default='OPEN')
    resolution_notes = models.TextField(blank=True, null=True)
    
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_exceptions')
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_exceptions')
    
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    claim_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        return f"{self.shipment.awb_number} - {self.get_exception_type_display()}"
    
    class Meta:
        ordering = ['-reported_at']


class Location(models.Model):
    LOCATION_TYPES = [
        ('WAREHOUSE', 'Warehouse'),
        ('OFFICE', 'Office'),
        ('AIRPORT', 'Airport'),
    ]
    
    name = models.CharField(max_length=200)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - {self.city}, {self.country}"


class StaffProfile(models.Model):
    ROLE_CHOICES = [
        ('BD_STAFF', 'Bangladesh Operations Staff'),
        ('BD_MANAGER', 'Bangladesh Manager'),
        ('HK_STAFF', 'Hong Kong Operations Staff'),
        ('HK_MANAGER', 'Hong Kong Manager'),
        ('DRIVER', 'Delivery Driver'),
        ('ADMIN', 'System Administrator'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True)
    phone = models.CharField(max_length=20)
    employee_id = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_role_display()}"