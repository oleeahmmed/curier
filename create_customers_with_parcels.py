"""
Script to create 2 customers and add 10 booked parcels for each
"""
import os
import django
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from exportimport.models import Customer, Shipment

def create_customers_with_parcels():
    """Create 2 customers and add 10 booked parcels for each"""
    
    # Customer data
    customers_data = [
        {
            'username': 'customer2',
            'password': '123456',
            'email': 'customer2@example.com',
            'first_name': 'Sarah',
            'last_name': 'Johnson',
            'customer_name': 'Sarah Johnson',
            'phone': '+880 1712-111222',
            'address': '456 Park Avenue, Dhaka 1200, Bangladesh',
            'country': 'Bangladesh',
        },
        {
            'username': 'customer3',
            'password': '123456',
            'email': 'customer3@example.com',
            'first_name': 'Michael',
            'last_name': 'Chen',
            'customer_name': 'Michael Chen',
            'phone': '+880 1712-333444',
            'address': '789 Lake Road, Chittagong 4000, Bangladesh',
            'country': 'Bangladesh',
        },
    ]
    
    # Parcel templates
    parcel_templates = [
        {
            'contents': 'Electronics - Smartphone and accessories',
            'weight': Decimal('1.5'),
            'value': Decimal('450.00'),
            'service_type': 'EXPRESS',
        },
        {
            'contents': 'Clothing - Designer garments',
            'weight': Decimal('2.8'),
            'value': Decimal('320.00'),
            'service_type': 'STANDARD',
        },
        {
            'contents': 'Books - Educational textbooks',
            'weight': Decimal('3.5'),
            'value': Decimal('120.00'),
            'service_type': 'STANDARD',
        },
        {
            'contents': 'Food items - Premium spices and tea',
            'weight': Decimal('2.0'),
            'value': Decimal('85.00'),
            'service_type': 'EXPRESS',
        },
        {
            'contents': 'Handicrafts - Traditional artwork',
            'weight': Decimal('4.2'),
            'value': Decimal('380.00'),
            'service_type': 'EXPRESS',
        },
        {
            'contents': 'Textiles - Silk fabrics',
            'weight': Decimal('3.8'),
            'value': Decimal('250.00'),
            'service_type': 'STANDARD',
        },
        {
            'contents': 'Personal care - Beauty products',
            'weight': Decimal('1.8'),
            'value': Decimal('110.00'),
            'service_type': 'EXPRESS',
        },
        {
            'contents': 'Documents - Important papers',
            'weight': Decimal('0.6'),
            'value': Decimal('40.00'),
            'service_type': 'EXPRESS',
        },
        {
            'contents': 'Jewelry - Gold accessories',
            'weight': Decimal('0.9'),
            'value': Decimal('850.00'),
            'service_type': 'EXPRESS',
        },
        {
            'contents': 'Home decor - Decorative items',
            'weight': Decimal('3.2'),
            'value': Decimal('180.00'),
            'service_type': 'STANDARD',
        },
    ]
    
    recipient_names = [
        'Alice Wong', 'Bob Chen', 'Carol Li', 'David Tam', 'Emma Zhang',
        'Frank Leung', 'Grace Ho', 'Henry Chow', 'Iris Lam', 'Jack Wu'
    ]
    
    # Get or create staff user for booking
    try:
        staff_user = User.objects.get(username='staff1')
    except User.DoesNotExist:
        staff_user = User.objects.create_user(
            username='staff1',
            password='123456',
            email='staff1@example.com',
            first_name='Staff',
            last_name='User',
            is_staff=True,
        )
        print(f"✓ Created staff user: staff1")
    
    total_customers_created = 0
    total_parcels_created = 0
    
    for customer_data in customers_data:
        # Create user
        username = customer_data['username']
        
        if User.objects.filter(username=username).exists():
            print(f"⚠ User '{username}' already exists, skipping...")
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(
                username=username,
                password=customer_data['password'],
                email=customer_data['email'],
                first_name=customer_data['first_name'],
                last_name=customer_data['last_name'],
                is_staff=False,
            )
            print(f"✓ Created user: {username}")
        
        # Create customer profile
        if hasattr(user, 'customer'):
            print(f"⚠ Customer profile for '{username}' already exists, using existing...")
            customer = user.customer
        else:
            customer = Customer.objects.create(
                user=user,
                name=customer_data['customer_name'],
                phone=customer_data['phone'],
                email=customer_data['email'],
                country=customer_data['country'],
                address=customer_data['address'],
                customer_type='REGULAR'
            )
            print(f"✓ Created customer profile: {customer_data['customer_name']}")
            total_customers_created += 1
        
        # Create 10 booked parcels
        print(f"\nCreating 10 booked parcels for {customer.name}...")
        
        for i in range(10):
            template = parcel_templates[i]
            recipient_name = recipient_names[i]
            
            try:
                shipment = Shipment.objects.create(
                    direction='BD_TO_HK',
                    customer=customer,
                    sender_name=customer.name,
                    sender_phone=customer.phone,
                    sender_address=customer.address,
                    sender_country=customer.country,
                    recipient_name=recipient_name,
                    recipient_phone=f'+852 9{200+i:03d}-{5678+i:04d}',
                    recipient_address=f'{(i+1)*15} Queen\'s Road, Central, Hong Kong',
                    recipient_country='Hong Kong',
                    contents=template['contents'],
                    declared_value=template['value'],
                    declared_currency='USD',
                    weight_estimated=template['weight'],
                    service_type=template['service_type'],
                    current_status='BOOKED',
                    payment_method='PREPAID',
                    payment_status='PAID',
                    booked_by=staff_user,
                )
                print(f"  ✓ Parcel {i+1}/10: {shipment.awb_number}")
                total_parcels_created += 1
            except Exception as e:
                print(f"  ✗ Failed to create parcel {i+1}/10: {e}")
        
        print()
    
    print("=" * 60)
    print(f"✓ Summary:")
    print(f"  - Customers created: {total_customers_created}")
    print(f"  - Parcels created: {total_parcels_created}")
    print(f"\nTest credentials:")
    print(f"  Customer 2: username=customer2, password=123456")
    print(f"  Customer 3: username=customer3, password=123456")
    print(f"  Staff: username=staff1, password=123456")

if __name__ == '__main__':
    create_customers_with_parcels()
