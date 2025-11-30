#!/usr/bin/env python3
"""
Demo Data Loader for BD-HK Logistics System
Run: python3 load_demo_data.py
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User, Group, Permission
from django.utils import timezone
from exportimport.models import (
    Location, StaffProfile, Customer, Shipment, Bag, 
    Manifest, TrackingEvent, DeliveryProof, ShipmentException
)


def create_groups_and_permissions():
    """Create user groups with permissions"""
    print("Creating user groups...")
    
    groups_data = {
        'Bangladesh Manager': ['add', 'change', 'delete', 'view'],
        'Bangladesh Staff': ['add', 'change', 'view'],
        'Hong Kong Manager': ['add', 'change', 'delete', 'view'],
        'Hong Kong Staff': ['add', 'change', 'view'],
        'Delivery Driver': ['view', 'change'],
        'Customer Service': ['add', 'view', 'change'],
    }
    
    for group_name, perms in groups_data.items():
        group, created = Group.objects.get_or_create(name=group_name)
        if created:
            print(f"  ✓ Created group: {group_name}")
        else:
            print(f"  - Group exists: {group_name}")


def create_users():
    """Create demo users"""
    print("\nCreating users...")
    
    users_data = [
        {'username': 'admin', 'email': 'admin@logistics.com', 'first_name': 'Admin', 'last_name': 'User', 'is_staff': True, 'is_superuser': True, 'password': 'admin123'},
        {'username': 'bd_manager', 'email': 'bd.manager@logistics.com', 'first_name': 'Karim', 'last_name': 'Rahman', 'is_staff': True, 'password': 'bd123', 'group': 'Bangladesh Manager'},
        {'username': 'bd_staff', 'email': 'bd.staff@logistics.com', 'first_name': 'Rahim', 'last_name': 'Ahmed', 'is_staff': True, 'password': 'bd123', 'group': 'Bangladesh Staff'},
        {'username': 'hk_manager', 'email': 'hk.manager@logistics.com', 'first_name': 'Wong', 'last_name': 'Chen', 'is_staff': True, 'password': 'hk123', 'group': 'Hong Kong Manager'},
        {'username': 'hk_staff', 'email': 'hk.staff@logistics.com', 'first_name': 'Li', 'last_name': 'Zhang', 'is_staff': True, 'password': 'hk123', 'group': 'Hong Kong Staff'},
        {'username': 'driver', 'email': 'driver@logistics.com', 'first_name': 'Hassan', 'last_name': 'Ali', 'is_staff': True, 'password': 'driver123', 'group': 'Delivery Driver'},
    ]
    
    created_users = {}
    for user_data in users_data:
        group_name = user_data.pop('group', None)
        password = user_data.pop('password')
        
        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults=user_data
        )
        
        if created:
            user.set_password(password)
            user.save()
            print(f"  ✓ Created user: {user.username} (password: {password})")
        else:
            print(f"  - User exists: {user.username}")
        
        if group_name:
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
        
        created_users[user.username] = user
    
    return created_users


def create_locations():
    """Create warehouse and office locations"""
    print("\nCreating locations...")
    
    locations_data = [
        {'name': 'Dhaka Main Warehouse', 'location_type': 'WAREHOUSE', 'country': 'Bangladesh', 'city': 'Dhaka', 'address': 'Uttara, Dhaka-1230', 'phone': '+880-1711-123456'},
        {'name': 'Dhaka Airport', 'location_type': 'AIRPORT', 'country': 'Bangladesh', 'city': 'Dhaka', 'address': 'Hazrat Shahjalal International Airport', 'phone': '+880-2-8901234'},
        {'name': 'Hong Kong Warehouse', 'location_type': 'WAREHOUSE', 'country': 'Hong Kong', 'city': 'Kowloon', 'address': 'Kwai Chung, Kowloon', 'phone': '+852-2345-6789'},
        {'name': 'Hong Kong Office', 'location_type': 'OFFICE', 'country': 'Hong Kong', 'city': 'Central', 'address': 'Central District, Hong Kong', 'phone': '+852-2345-6700'},
    ]
    
    created_locations = {}
    for loc_data in locations_data:
        location, created = Location.objects.get_or_create(
            name=loc_data['name'],
            defaults=loc_data
        )
        if created:
            print(f"  ✓ Created location: {location.name}")
        else:
            print(f"  - Location exists: {location.name}")
        created_locations[location.name] = location
    
    return created_locations


def create_staff_profiles(users, locations):
    """Create staff profiles"""
    print("\nCreating staff profiles...")
    
    profiles_data = [
        {'user': users['bd_manager'], 'role': 'BD_MANAGER', 'location': locations['Dhaka Main Warehouse'], 'phone': '+880-1711-111111', 'employee_id': 'BD-MGR-001'},
        {'user': users['bd_staff'], 'role': 'BD_STAFF', 'location': locations['Dhaka Main Warehouse'], 'phone': '+880-1711-222222', 'employee_id': 'BD-STF-001'},
        {'user': users['hk_manager'], 'role': 'HK_MANAGER', 'location': locations['Hong Kong Warehouse'], 'phone': '+852-9123-4567', 'employee_id': 'HK-MGR-001'},
        {'user': users['hk_staff'], 'role': 'HK_STAFF', 'location': locations['Hong Kong Warehouse'], 'phone': '+852-9123-4568', 'employee_id': 'HK-STF-001'},
        {'user': users['driver'], 'role': 'DRIVER', 'location': locations['Dhaka Main Warehouse'], 'phone': '+880-1711-333333', 'employee_id': 'BD-DRV-001'},
    ]
    
    for profile_data in profiles_data:
        profile, created = StaffProfile.objects.get_or_create(
            user=profile_data['user'],
            defaults=profile_data
        )
        if created:
            print(f"  ✓ Created profile: {profile.user.username}")
        else:
            print(f"  - Profile exists: {profile.user.username}")


def create_customers(users):
    """Create demo customers"""
    print("\nCreating customers...")
    
    customers_data = [
        {'name': 'Md. Kamal Hossain', 'phone': '+880-1712-345678', 'email': 'kamal@example.com', 'address': 'Mirpur-10, Dhaka', 'customer_type': 'REGULAR'},
        {'name': 'Fatima Begum', 'phone': '+880-1713-456789', 'email': 'fatima@example.com', 'address': 'Dhanmondi, Dhaka', 'customer_type': 'REGULAR'},
        {'name': 'Abdul Rahman', 'phone': '+880-1714-567890', 'email': 'rahman@example.com', 'address': 'Gulshan-2, Dhaka', 'customer_type': 'CREDIT'},
        {'name': 'Nasrin Akter', 'phone': '+880-1715-678901', 'email': 'nasrin@example.com', 'address': 'Banani, Dhaka', 'customer_type': 'REGULAR'},
        {'name': 'Wong Tai Sin', 'phone': '+852-9234-5678', 'email': 'wong@example.com', 'address': 'Mong Kok, Kowloon', 'customer_type': 'REGULAR'},
        {'name': 'Li Ming', 'phone': '+852-9234-5679', 'email': 'liming@example.com', 'address': 'Tsim Sha Tsui, Kowloon', 'customer_type': 'CREDIT'},
    ]
    
    created_customers = []
    for cust_data in customers_data:
        customer, created = Customer.objects.get_or_create(
            phone=cust_data['phone'],
            defaults=cust_data
        )
        if created:
            print(f"  ✓ Created customer: {customer.name}")
        else:
            print(f"  - Customer exists: {customer.name}")
        created_customers.append(customer)
    
    return created_customers


def create_shipments_bd_to_hk(customers, users):
    """Create BD → HK shipments"""
    print("\nCreating BD → HK shipments...")
    
    shipments_data = [
        {
            'customer': customers[0],
            'sender_name': 'Md. Kamal Hossain',
            'sender_phone': '+880-1712-345678',
            'sender_address': 'Mirpur-10, Dhaka',
            'recipient_name': 'Chan Tai Man',
            'recipient_phone': '+852-9111-2222',
            'recipient_address': 'Flat 5A, Block 3, Mei Foo Sun Chuen, Kowloon',
            'contents': 'Clothing and personal items',
            'declared_value': Decimal('150.00'),
            'weight_estimated': Decimal('5.5'),
            'service_type': 'EXPRESS',
            'payment_method': 'PREPAID',
            'current_status': 'BOOKED',
        },
        {
            'customer': customers[1],
            'sender_name': 'Fatima Begum',
            'sender_phone': '+880-1713-456789',
            'sender_address': 'Dhanmondi, Dhaka',
            'recipient_name': 'Wong Siu Ming',
            'recipient_phone': '+852-9222-3333',
            'recipient_address': 'Room 1203, Tower 2, Taikoo Shing, Hong Kong',
            'contents': 'Books and documents',
            'declared_value': Decimal('80.00'),
            'weight_estimated': Decimal('3.2'),
            'service_type': 'STANDARD',
            'payment_method': 'CASH',
            'current_status': 'RECEIVED_AT_BD',
        },
        {
            'customer': customers[2],
            'sender_name': 'Abdul Rahman',
            'sender_phone': '+880-1714-567890',
            'sender_address': 'Gulshan-2, Dhaka',
            'recipient_name': 'Li Xiao Hong',
            'recipient_phone': '+852-9333-4444',
            'recipient_address': 'Unit 8B, Kornhill Gardens, Quarry Bay',
            'contents': 'Electronics and accessories',
            'declared_value': Decimal('500.00'),
            'weight_estimated': Decimal('8.0'),
            'service_type': 'EXPRESS',
            'payment_method': 'CREDIT',
            'current_status': 'READY_FOR_SORTING',
        },
    ]
    
    created_shipments = []
    for ship_data in shipments_data:
        ship_data['direction'] = 'BD_TO_HK'
        ship_data['booked_by'] = users['bd_staff']
        
        shipment = Shipment.objects.create(**ship_data)
        print(f"  ✓ Created shipment: {shipment.awb_number}")
        created_shipments.append(shipment)
    
    return created_shipments


def create_shipments_hk_to_bd(customers, users):
    """Create HK → BD shipments"""
    print("\nCreating HK → BD shipments...")
    
    # Get HK customers (last 2 in the list)
    hk_customers = customers[-2:] if len(customers) >= 2 else customers
    
    shipments_data = [
        {
            'customer': hk_customers[0] if len(hk_customers) > 0 else None,
            'sender_name': 'Wong Tai Sin',
            'sender_phone': '+852-9234-5678',
            'sender_address': 'Mong Kok, Kowloon',
            'recipient_name': 'Md. Rafiq',
            'recipient_phone': '+880-1716-789012',
            'recipient_address': 'Mohammadpur, Dhaka-1207',
            'contents': 'Mobile phones and accessories',
            'declared_value': Decimal('800.00'),
            'weight_estimated': Decimal('2.5'),
            'service_type': 'EXPRESS',
            'payment_method': 'COD',
            'is_cod': True,
            'cod_amount': Decimal('85000.00'),
            'current_status': 'IN_TRANSIT_TO_BD',
            'hk_reference': 'HK-REF-12345',
        },
        {
            'customer': hk_customers[1] if len(hk_customers) > 1 else hk_customers[0] if len(hk_customers) > 0 else None,
            'sender_name': 'Li Ming',
            'sender_phone': '+852-9234-5679',
            'sender_address': 'Tsim Sha Tsui, Kowloon',
            'recipient_name': 'Ayesha Siddiqua',
            'recipient_phone': '+880-1717-890123',
            'recipient_address': 'Uttara Sector-7, Dhaka',
            'contents': 'Fashion items and cosmetics',
            'declared_value': Decimal('300.00'),
            'weight_estimated': Decimal('4.0'),
            'service_type': 'STANDARD',
            'payment_method': 'PREPAID',
            'current_status': 'ARRIVED_AT_BD',
            'hk_reference': 'HK-REF-12346',
        },
    ]
    
    created_shipments = []
    for ship_data in shipments_data:
        ship_data['direction'] = 'HK_TO_BD'
        ship_data['booked_by'] = users['hk_staff']
        
        shipment = Shipment.objects.create(**ship_data)
        print(f"  ✓ Created shipment: {shipment.awb_number}")
        created_shipments.append(shipment)
    
    return created_shipments


def create_bags_and_assign_shipments(shipments, users):
    """Create bags and assign shipments"""
    print("\nCreating bags...")
    
    # Only bag BD → HK shipments
    bd_shipments = [s for s in shipments if s.direction == 'BD_TO_HK']
    
    if bd_shipments:
        bag = Bag.objects.create(
            bag_number='BAG-20241122-001',
            status='OPEN',
            total_parcels=len(bd_shipments),
            total_weight=sum(s.weight_estimated for s in bd_shipments)
        )
        print(f"  ✓ Created bag: {bag.bag_number}")
        
        # Assign shipments to bag
        for shipment in bd_shipments:
            shipment.bag = bag
            shipment.current_status = 'BAGGED_FOR_EXPORT'
            shipment.save()
        
        print(f"  ✓ Assigned {len(bd_shipments)} shipments to bag")
        
        return bag
    
    return None


def create_manifest(bag, users):
    """Create manifest"""
    if not bag:
        return None
    
    print("\nCreating manifest...")
    
    tomorrow = timezone.now().date() + timedelta(days=1)
    
    manifest = Manifest.objects.create(
        flight_number='BG-088',
        departure_date=tomorrow,
        departure_time='23:30',
        mawb_number='MAWB-12345678',
        total_bags=1,
        total_parcels=bag.total_parcels,
        total_weight=bag.total_weight,
        status='DRAFT',
        created_by=users['bd_manager']
    )
    
    manifest.bags.add(bag)
    print(f"  ✓ Created manifest: {manifest.manifest_number}")
    
    return manifest


def create_tracking_events(shipments, users):
    """Create tracking events"""
    print("\nCreating tracking events...")
    
    count = 0
    for shipment in shipments:
        if shipment.direction == 'BD_TO_HK':
            events = [
                {'status': 'BOOKED', 'location': 'Dhaka Office', 'description': 'Shipment booked'},
                {'status': 'RECEIVED_AT_BD', 'location': 'Dhaka Warehouse', 'description': 'Received at warehouse'},
            ]
        else:
            events = [
                {'status': 'BOOKED', 'location': 'Hong Kong Office', 'description': 'Shipment booked'},
                {'status': 'IN_TRANSIT_TO_BD', 'location': 'In Transit', 'description': 'On flight to Bangladesh'},
            ]
        
        for event_data in events:
            TrackingEvent.objects.create(
                shipment=shipment,
                status=event_data['status'],
                location=event_data['location'],
                description=event_data['description'],
                updated_by=users['bd_staff']
            )
            count += 1
    
    print(f"  ✓ Created {count} tracking events")


def create_exceptions(shipments, users):
    """Create sample exceptions"""
    print("\nCreating exceptions...")
    
    if len(shipments) > 0:
        exception = ShipmentException.objects.create(
            shipment=shipments[0],
            exception_type='WEIGHT_DISCREPANCY',
            description='Actual weight differs from declared weight',
            resolution_status='OPEN',
            reported_by=users['bd_staff']
        )
        print(f"  ✓ Created exception for: {exception.shipment.awb_number}")


def main():
    """Main execution"""
    print("=" * 60)
    print("BD-HK LOGISTICS DEMO DATA LOADER")
    print("=" * 60)
    
    try:
        # Step 1: Groups
        create_groups_and_permissions()
        
        # Step 2: Users
        users = create_users()
        
        # Step 3: Locations
        locations = create_locations()
        
        # Step 4: Staff Profiles
        create_staff_profiles(users, locations)
        
        # Step 5: Customers
        customers = create_customers(users)
        
        # Step 6: Shipments
        bd_shipments = create_shipments_bd_to_hk(customers, users)
        hk_shipments = create_shipments_hk_to_bd(customers, users)
        all_shipments = bd_shipments + hk_shipments
        
        # Step 7: Bags
        bag = create_bags_and_assign_shipments(bd_shipments, users)
        
        # Step 8: Manifest
        manifest = create_manifest(bag, users)
        
        # Step 9: Tracking Events
        create_tracking_events(all_shipments, users)
        
        # Step 10: Exceptions
        create_exceptions(all_shipments, users)
        
        print("\n" + "=" * 60)
        print("✓ DEMO DATA LOADED SUCCESSFULLY!")
        print("=" * 60)
        print("\nLogin Credentials:")
        print("  Admin:        admin / admin123")
        print("  BD Manager:   bd_manager / bd123")
        print("  BD Staff:     bd_staff / bd123")
        print("  HK Manager:   hk_manager / hk123")
        print("  HK Staff:     hk_staff / hk123")
        print("  Driver:       driver / driver123")
        print("\nAccess admin at: http://localhost:8000/admin/")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
