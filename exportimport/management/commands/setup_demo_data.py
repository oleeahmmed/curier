from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from exportimport.models import Customer, Shipment
from decimal import Decimal


class Command(BaseCommand):
    help = 'Populate database with demo/test data for development'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing demo data before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting demo data setup...'))
        
        # Clear existing demo data if requested
        if options['clear']:
            self.clear_demo_data()
        
        # Create users
        customer_user = self.create_customer_user()
        staff_user = self.create_staff_user()
        
        # Create customer profile
        customer = self.create_customer_profile(customer_user)
        
        # Create shipments
        self.create_pending_shipments(customer)
        self.create_booked_shipments(customer, staff_user)
        self.create_workflow_shipments(customer, staff_user)
        
        self.stdout.write(self.style.SUCCESS('\\n✓ Demo data setup complete!'))
        self.stdout.write(self.style.SUCCESS('\\nTest credentials:'))
        self.stdout.write(self.style.SUCCESS('  Customer: username=customer1, password=123456'))
        self.stdout.write(self.style.SUCCESS('  Staff: username=staff1, password=123456'))

    def clear_demo_data(self):
        """Clear existing demo users and their shipments"""
        self.stdout.write('\\nClearing existing demo data...')
        
        # Delete demo users and their related data (cascades to shipments)
        deleted_users = 0
        for username in ['customer1', 'staff1']:
            try:
                user = User.objects.get(username=username)
                # Delete associated shipments first
                if hasattr(user, 'customer'):
                    shipment_count = Shipment.objects.filter(customer=user.customer).count()
                    Shipment.objects.filter(customer=user.customer).delete()
                    self.stdout.write(f'  ✓ Deleted {shipment_count} shipments for {username}')
                user.delete()
                deleted_users += 1
                self.stdout.write(f'  ✓ Deleted user: {username}')
            except User.DoesNotExist:
                pass
        
        if deleted_users == 0:
            self.stdout.write(self.style.WARNING('  No existing demo data found'))

    def create_customer_user(self):
        """Create customer user (non-staff, non-admin)"""
        username = 'customer1'
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists, skipping...'))
            return User.objects.get(username=username)
        
        user = User.objects.create_user(
            username=username,
            password='123456',
            email='customer1@example.com',
            first_name='John',
            last_name='Doe',
            is_staff=False,
            is_superuser=False
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created customer user: {username}'))
        return user

    def create_staff_user(self):
        """Create staff user (staff but not admin)"""
        username = 'staff1'
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists, skipping...'))
            return User.objects.get(username=username)
        
        user = User.objects.create_user(
            username=username,
            password='123456',
            email='staff1@example.com',
            first_name='Jane',
            last_name='Smith',
            is_staff=True,
            is_superuser=False
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created staff user: {username}'))
        return user

    def create_customer_profile(self, user):
        """Create Customer profile for the customer user"""
        if hasattr(user, 'customer'):
            self.stdout.write(self.style.WARNING(f'Customer profile for "{user.username}" already exists, skipping...'))
            return user.customer
        
        customer = Customer.objects.create(
            user=user,
            name='John Doe',
            phone='+880 1712-345678',
            email='customer1@example.com',
            country='Bangladesh',
            address='123 Main Street, Dhaka 1000, Bangladesh',
            customer_type='REGULAR'
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created customer profile for: {user.username}'))
        return customer

    def create_pending_shipments(self, customer):
        """Create 3-4 shipments with PENDING status"""
        self.stdout.write('\\nCreating PENDING shipments...')
        
        pending_data = [
            {
                'contents': 'Electronics - Mobile phone accessories',
                'weight': Decimal('1.5'),
                'value': Decimal('150.00'),
                'recipient_name': 'Alice Wong',
                'recipient_phone': '+852 9123-4567',
            },
            {
                'contents': 'Clothing - Traditional sarees and fabrics',
                'weight': Decimal('2.8'),
                'value': Decimal('250.00'),
                'recipient_name': 'Bob Chen',
                'recipient_phone': '+852 9234-5678',
            },
            {
                'contents': 'Books and educational materials',
                'weight': Decimal('3.2'),
                'value': Decimal('80.00'),
                'recipient_name': 'Carol Li',
                'recipient_phone': '+852 9345-6789',
            },
            {
                'contents': 'Food items - Spices and snacks',
                'weight': Decimal('1.0'),
                'value': Decimal('45.00'),
                'recipient_name': 'David Tam',
                'recipient_phone': '+852 9456-7890',
            },
        ]
        
        for i, data in enumerate(pending_data, 1):
            shipment = Shipment.objects.create(
                direction='BD_TO_HK',
                customer=customer,
                sender_name=customer.name,
                sender_phone=customer.phone,
                sender_address=customer.address,
                sender_country='Bangladesh',
                recipient_name=data['recipient_name'],
                recipient_phone=data['recipient_phone'],
                recipient_address=f'{i*10} Nathan Road, Kowloon, Hong Kong',
                recipient_country='Hong Kong',
                contents=data['contents'],
                declared_value=data['value'],
                declared_currency='USD',
                weight_estimated=data['weight'],
                service_type='EXPRESS' if i % 2 == 0 else 'STANDARD',
                current_status='PENDING',
                payment_method='PREPAID' if i % 2 == 0 else 'CASH',
                payment_status='PENDING',
            )
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created PENDING shipment #{i}'))

    def create_booked_shipments(self, customer, staff_user):
        """Create 2-3 shipments with BOOKED status and AWB numbers"""
        self.stdout.write('\\nCreating BOOKED shipments...')
        
        booked_data = [
            {
                'contents': 'Handicrafts - Decorative items',
                'weight': Decimal('4.5'),
                'value': Decimal('320.00'),
                'recipient_name': 'Emma Zhang',
                'recipient_phone': '+852 9567-8901',
                'payment_status': 'PAID',
            },
            {
                'contents': 'Textiles - Bed sheets and curtains',
                'weight': Decimal('5.2'),
                'value': Decimal('180.00'),
                'recipient_name': 'Frank Leung',
                'recipient_phone': '+852 9678-9012',
                'payment_status': 'PAID',
            },
            {
                'contents': 'Personal items - Cosmetics and toiletries',
                'weight': Decimal('2.1'),
                'value': Decimal('95.00'),
                'recipient_name': 'Grace Ho',
                'recipient_phone': '+852 9789-0123',
                'payment_status': 'PENDING',
            },
        ]
        
        for i, data in enumerate(booked_data, 1):
            # Retry up to 3 times if AWB collision occurs
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    shipment = Shipment.objects.create(
                        direction='BD_TO_HK',
                        customer=customer,
                        sender_name=customer.name,
                        sender_phone=customer.phone,
                        sender_address=customer.address,
                        sender_country='Bangladesh',
                        recipient_name=data['recipient_name'],
                        recipient_phone=data['recipient_phone'],
                        recipient_address=f'{i*20} Queen\'s Road, Central, Hong Kong',
                        recipient_country='Hong Kong',
                        contents=data['contents'],
                        declared_value=data['value'],
                        declared_currency='USD',
                        weight_estimated=data['weight'],
                        service_type='EXPRESS',
                        current_status='BOOKED',
                        payment_method='PREPAID',
                        payment_status=data['payment_status'],
                        booked_by=staff_user,
                    )
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created BOOKED shipment: {shipment.awb_number}'))
                    break
                except Exception as e:
                    if 'UNIQUE constraint failed' in str(e) and attempt < max_retries - 1:
                        self.stdout.write(self.style.WARNING(f'  AWB collision, retrying... (attempt {attempt + 1})'))
                        continue
                    else:
                        self.stdout.write(self.style.ERROR(f'  ✗ Failed to create BOOKED shipment: {e}'))
                        break

    def create_workflow_shipments(self, customer, staff_user):
        """Create shipments in various workflow states"""
        self.stdout.write('\\nCreating shipments in various workflow states...')
        
        workflow_data = [
            {
                'status': 'RECEIVED_AT_BD',
                'contents': 'Documents - Legal papers and certificates',
                'weight_estimated': Decimal('0.8'),
                'weight_actual': Decimal('0.85'),
                'value': Decimal('50.00'),
                'recipient_name': 'Henry Chow',
                'recipient_phone': '+852 9890-1234',
            },
            {
                'status': 'READY_FOR_SORTING',
                'contents': 'Jewelry - Fashion accessories',
                'weight_estimated': Decimal('0.5'),
                'weight_actual': Decimal('0.52'),
                'value': Decimal('420.00'),
                'recipient_name': 'Iris Lam',
                'recipient_phone': '+852 9901-2345',
            },
        ]
        
        for data in workflow_data:
            # Retry up to 3 times if AWB collision occurs
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    shipment = Shipment.objects.create(
                        direction='BD_TO_HK',
                        customer=customer,
                        sender_name=customer.name,
                        sender_phone=customer.phone,
                        sender_address=customer.address,
                        sender_country='Bangladesh',
                        recipient_name=data['recipient_name'],
                        recipient_phone=data['recipient_phone'],
                        recipient_address='88 Hennessy Road, Wan Chai, Hong Kong',
                        recipient_country='Hong Kong',
                        contents=data['contents'],
                        declared_value=data['value'],
                        declared_currency='USD',
                        weight_estimated=data['weight_estimated'],
                        weight_actual=data.get('weight_actual'),
                        service_type='EXPRESS',
                        current_status=data['status'],
                        payment_method='PREPAID',
                        payment_status='PAID',
                        booked_by=staff_user,
                    )
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created {data["status"]} shipment: {shipment.awb_number}'))
                    break
                except Exception as e:
                    if 'UNIQUE constraint failed' in str(e) and attempt < max_retries - 1:
                        self.stdout.write(self.style.WARNING(f'  AWB collision, retrying... (attempt {attempt + 1})'))
                        continue
                    else:
                        self.stdout.write(self.style.ERROR(f'  ✗ Failed to create {data["status"]} shipment: {e}'))
                        break
