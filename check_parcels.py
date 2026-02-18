import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from exportimport.models import Shipment, Customer
from django.db.models import Count, Q

print('=' * 60)
print('PARCELS BY CUSTOMER')
print('=' * 60)
print()

customers = Customer.objects.annotate(
    total_parcels=Count('shipments'),
    with_awb=Count('shipments', filter=Q(shipments__awb_number__isnull=False) & ~Q(shipments__awb_number='')),
    without_awb=Count('shipments', filter=Q(shipments__awb_number__isnull=True) | Q(shipments__awb_number=''))
)

for c in customers:
    if c.total_parcels > 0:
        print(f'Customer: {c.name} ({c.phone})')
        print(f'  Total Parcels: {c.total_parcels}')
        print(f'  With AWB: {c.with_awb}')
        print(f'  Without AWB (PENDING): {c.without_awb}')
        print()

print('=' * 60)
print('SUMMARY')
print('=' * 60)
print(f'Total Customers: {Customer.objects.count()}')
print(f'Customers with parcels: {Customer.objects.annotate(pc=Count("shipments")).filter(pc__gt=0).count()}')
print(f'Total Parcels: {Shipment.objects.count()}')
print(f'Parcels with AWB: {Shipment.objects.filter(awb_number__isnull=False).exclude(awb_number="").count()}')
print(f'Parcels without AWB (PENDING): {Shipment.objects.filter(Q(awb_number__isnull=True) | Q(awb_number="")).count()}')
print(f'Parcels with no customer assigned: {Shipment.objects.filter(customer__isnull=True).count()}')
print()

# Show status breakdown
print('=' * 60)
print('PARCELS BY STATUS')
print('=' * 60)
statuses = Shipment.objects.values('current_status').annotate(count=Count('id')).order_by('-count')
for s in statuses:
    print(f'{s["current_status"]}: {s["count"]}')
