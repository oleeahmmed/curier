from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


# ==================== CUSTOMER ====================
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


# ==================== SHIPMENT ====================
class Shipment(models.Model):
    # Direction
    DIRECTION_CHOICES = [
        ('BD_TO_HK', 'Bangladesh to Hong Kong'),
    ]
    
    # Status for BD → HK
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
    
    # Combined Status
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
    
    # === BASIC INFO ===
    awb_number = models.CharField(max_length=50, unique=True, editable=False, blank=True, null=True)
    external_awb = models.CharField(max_length=50, blank=True, null=True, help_text="External AWB (from HK/Airline)")
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='shipments', null=True, blank=True)
    
    # === SENDER INFO ===
    sender_name = models.CharField(max_length=200)
    sender_phone = models.CharField(max_length=20)
    sender_address = models.TextField()
    sender_country = models.CharField(max_length=100, default='Bangladesh')
    
    # === RECIPIENT INFO ===
    recipient_name = models.CharField(max_length=200)
    recipient_phone = models.CharField(max_length=20)
    recipient_address = models.TextField()
    recipient_country = models.CharField(max_length=100, default='Hong Kong')
    
    # === PARCEL DETAILS ===
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
    
    # === SERVICE & STATUS ===
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, default='EXPRESS')
    current_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='BOOKED')
    
    # === PAYMENT ===
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
    
    # COD
    is_cod = models.BooleanField(default=False)
    cod_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # === SPECIAL HANDLING ===
    is_fragile = models.BooleanField(default=False)
    is_liquid = models.BooleanField(default=False)
    special_instructions = models.TextField(blank=True, null=True)
    
    # === LINKING (For BD → HK) ===
    # Removed: bag ForeignKey - now using ManyToMany from Bag model
    
    # === HK REFERENCE (For HK → BD) ===
    hk_reference = models.CharField(max_length=100, blank=True, null=True, help_text="HK warehouse reference")
    mawb_number = models.CharField(max_length=50, blank=True, null=True, help_text="Master AWB")
    
    # === TIMESTAMPS ===
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    booked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='booked_shipments')
    
    def save(self, *args, **kwargs):
        # Generate AWB only if status is not PENDING and AWB doesn't exist
        if not self.awb_number and self.current_status != 'PENDING':
            # Generate AWB based on direction
            date_str = timezone.now().strftime('%Y%m%d')
            random_num = str(uuid.uuid4().int)[:5]
            
            if self.direction == 'BD_TO_HK':
                self.awb_number = f"DH{date_str}{random_num}"  # Dhaka to HK
            else:
                self.awb_number = f"HD{date_str}{random_num}"  # HK to Dhaka
        
        # Auto-set sender/recipient country based on direction
        if self.direction == 'BD_TO_HK':
            self.sender_country = 'Bangladesh'
            self.recipient_country = 'Hong Kong'
        else:
            self.sender_country = 'Hong Kong'
            self.recipient_country = 'Bangladesh'
        
        super().save(*args, **kwargs)
    
    def get_qrcode_url(self):
        """Generate QR code data URL for AWB number"""
        import qrcode
        import io
        import base64
        
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
        """Generate barcode data URL for AWB number"""
        import barcode
        from barcode.writer import ImageWriter
        import io
        import base64
        
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


# ==================== BAG (Only for BD → HK) ====================
class Bag(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('SEALED', 'Sealed'),
        ('IN_MANIFEST', 'In Manifest'),
        ('DISPATCHED', 'Dispatched'),
    ]
    
    bag_number = models.CharField(max_length=50, unique=True)
    shipment = models.OneToOneField('Shipment', on_delete=models.CASCADE, related_name='bag', null=True, blank=True, help_text="One shipment per bag")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    weight = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Bag weight in KG")
    
    sealed_at = models.DateTimeField(null=True, blank=True)
    sealed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sealed_bags')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def get_qrcode_url(self):
        """Generate QR code - same as shipment's AWB"""
        if self.shipment:
            return self.shipment.get_qrcode_url()
        
        # If no shipment, generate for bag number
        import qrcode
        import io
        import base64
        
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
        """Generate barcode - same as shipment's AWB"""
        if self.shipment:
            return self.shipment.get_barcode_url()
        
        # If no shipment, generate for bag number
        import barcode
        from barcode.writer import ImageWriter
        import io
        import base64
        
        code128 = barcode.get_barcode_class('code128')
        barcode_instance = code128(self.bag_number, writer=ImageWriter())
        
        buffer = io.BytesIO()
        barcode_instance.write(buffer)
        buffer.seek(0)
        
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def seal_bag(self, user):
        self.status = 'SEALED'
        self.sealed_at = timezone.now()
        self.sealed_by = user
        self.save()
    
    def __str__(self):
        if self.shipment:
            return f"{self.bag_number} - {self.shipment.awb_number}"
        return f"{self.bag_number}"
    
    class Meta:
        ordering = ['-created_at']


# ==================== MANIFEST (Only for BD → HK) ====================
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
    
    def finalize_manifest(self, user):
        self.status = 'FINALIZED'
        self.finalized_by = user
        self.finalized_at = timezone.now()
        
        # Update bags
        for bag in self.bags.all():
            bag.status = 'IN_MANIFEST'
            bag.save()
            
            # Update shipments
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


# ==================== TRACKING EVENTS ====================
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


# ==================== DELIVERY PROOF ====================
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


# ==================== EXCEPTIONS ====================
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


# ==================== LOCATION ====================
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


# ==================== STAFF PROFILE ====================
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