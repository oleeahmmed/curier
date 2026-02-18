from django.test import TestCase
from django.contrib.auth.models import User
from .models import Bag


class BagSaveMethodTestCase(TestCase):
    """Test the save method auto-generates bag_number"""
    
    def test_save_generates_bag_number_when_empty(self):
        """Test that save() generates bag_number when not set"""
        bag = Bag.objects.create(status='OPEN')
        
        # Verify bag_number was auto-generated
        self.assertIsNotNone(bag.bag_number)
        self.assertTrue(bag.bag_number.startswith('HDK-BAG-'))
        
    def test_save_preserves_existing_bag_number(self):
        """Test that save() doesn't change existing bag_number"""
        bag = Bag.objects.create(bag_number='HDK-BAG-999999', status='OPEN')
        original_number = bag.bag_number
        
        # Modify and save again
        bag.status = 'SEALED'
        bag.save()
        
        # Verify bag_number unchanged
        self.assertEqual(bag.bag_number, original_number)
        
    def test_first_bag_number_is_000001(self):
        """Test that first bag gets HDK-BAG-000001"""
        bag = Bag.objects.create(status='OPEN')
        
        self.assertEqual(bag.bag_number, 'HDK-BAG-000001')
        
    def test_sequential_bag_numbers(self):
        """Test that bag numbers are sequential"""
        bag1 = Bag.objects.create(status='OPEN')
        bag2 = Bag.objects.create(status='OPEN')
        bag3 = Bag.objects.create(status='OPEN')
        
        self.assertEqual(bag1.bag_number, 'HDK-BAG-000001')
        self.assertEqual(bag2.bag_number, 'HDK-BAG-000002')
        self.assertEqual(bag3.bag_number, 'HDK-BAG-000003')


class BagDeleteMethodTestCase(TestCase):
    """Test the delete method handles OPEN bags correctly"""
    
    def setUp(self):
        """Set up test data"""
        from .models import Shipment, TrackingEvent
        
        # Create a user for tracking events
        self.user = User.objects.create_user(username='testuser', password='testpass')
        
        # Create an OPEN bag
        self.open_bag = Bag.objects.create(bag_number='HDK-BAG-TEST001', status='OPEN')
        
        # Create shipments and add to bag
        self.shipment1 = Shipment.objects.create(
            awb_number='AWB001',
            current_status='BAGGED_FOR_EXPORT',
            direction='BD_TO_HK',
            sender_name='Test Sender 1',
            sender_phone='+8801234567890',
            sender_address='123 Test St, Dhaka',
            recipient_name='Test Recipient 1',
            recipient_phone='+85212345678',
            recipient_address='456 Test Rd, Hong Kong',
            contents='Test items',
            declared_value=100.00,
            weight_estimated=2.5,
            payment_method='PREPAID'
        )
        self.shipment2 = Shipment.objects.create(
            awb_number='AWB002',
            current_status='BAGGED_FOR_EXPORT',
            direction='BD_TO_HK',
            sender_name='Test Sender 2',
            sender_phone='+8801234567891',
            sender_address='789 Test Ave, Dhaka',
            recipient_name='Test Recipient 2',
            recipient_phone='+85212345679',
            recipient_address='789 Test Blvd, Hong Kong',
            contents='Test items 2',
            declared_value=150.00,
            weight_estimated=3.0,
            payment_method='PREPAID'
        )
        
        self.open_bag.shipment.add(self.shipment1, self.shipment2)
    
    def test_delete_open_bag_succeeds(self):
        """Test that deleting an OPEN bag succeeds"""
        from .models import Shipment
        
        bag_id = self.open_bag.id
        shipment1_id = self.shipment1.id
        shipment2_id = self.shipment2.id
        
        # Delete the bag
        self.open_bag.delete()
        
        # Verify bag is deleted
        self.assertFalse(Bag.objects.filter(id=bag_id).exists())
        
        # Verify shipments still exist and status reverted
        shipment1 = Shipment.objects.get(id=shipment1_id)
        shipment2 = Shipment.objects.get(id=shipment2_id)
        
        self.assertEqual(shipment1.current_status, 'RECEIVED_AT_BD')
        self.assertEqual(shipment2.current_status, 'RECEIVED_AT_BD')
    
    def test_delete_sealed_bag_raises_error(self):
        """Test that deleting a SEALED bag raises ValidationError"""
        from django.core.exceptions import ValidationError
        
        sealed_bag = Bag.objects.create(bag_number='HDK-BAG-TEST002', status='SEALED')
        
        with self.assertRaises(ValidationError) as context:
            sealed_bag.delete()
        
        self.assertIn('Cannot delete bag with status SEALED', str(context.exception))
    
    def test_delete_in_manifest_bag_raises_error(self):
        """Test that deleting an IN_MANIFEST bag raises ValidationError"""
        from django.core.exceptions import ValidationError
        
        manifest_bag = Bag.objects.create(bag_number='HDK-BAG-TEST003', status='IN_MANIFEST')
        
        with self.assertRaises(ValidationError) as context:
            manifest_bag.delete()
        
        self.assertIn('Cannot delete bag with status IN_MANIFEST', str(context.exception))
    
    def test_delete_dispatched_bag_raises_error(self):
        """Test that deleting a DISPATCHED bag raises ValidationError"""
        from django.core.exceptions import ValidationError
        
        dispatched_bag = Bag.objects.create(bag_number='HDK-BAG-TEST004', status='DISPATCHED')
        
        with self.assertRaises(ValidationError) as context:
            dispatched_bag.delete()
        
        self.assertIn('Cannot delete bag with status DISPATCHED', str(context.exception))
    
    def test_delete_creates_tracking_events(self):
        """Test that deleting a bag creates tracking events for shipments"""
        from .models import TrackingEvent
        
        # Count tracking events before deletion
        events_before = TrackingEvent.objects.count()
        
        # Delete the bag
        self.open_bag.delete()
        
        # Verify tracking events were created (2 shipments = 2 events)
        events_after = TrackingEvent.objects.count()
        self.assertEqual(events_after, events_before + 2)
        
        # Verify event details
        events = TrackingEvent.objects.filter(
            shipment__in=[self.shipment1.id, self.shipment2.id]
        ).order_by('id')
        
        for event in events:
            self.assertEqual(event.status, 'RECEIVED_AT_BD')
            self.assertIn('Removed from deleted bag HDK-BAG-TEST001', event.description)
            self.assertEqual(event.location, 'Bangladesh Warehouse')
            self.assertIsNone(event.updated_by)



class BagAdminDeleteTestCase(TestCase):
    """Test the BagAdmin delete_model method handles validation errors"""
    
    def setUp(self):
        """Set up test data"""
        from django.contrib.admin.sites import AdminSite
        from .admin import BagAdmin
        from django.test import RequestFactory
        from django.contrib.auth.models import User
        from django.contrib.messages.storage.fallback import FallbackStorage
        
        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass'
        )
        
        # Create BagAdmin instance
        self.site = AdminSite()
        self.bag_admin = BagAdmin(Bag, self.site)
        
        # Create request factory
        self.factory = RequestFactory()
        
    def test_delete_model_with_open_bag_succeeds(self):
        """Test that delete_model succeeds for OPEN bags"""
        from django.contrib.messages.storage.fallback import FallbackStorage
        
        # Create an OPEN bag
        bag = Bag.objects.create(bag_number='HDK-BAG-TEST100', status='OPEN')
        
        # Create a mock request
        request = self.factory.post('/admin/exportimport/bag/')
        request.user = self.admin_user
        
        # Add messages framework support
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        # Call delete_model
        self.bag_admin.delete_model(request, bag)
        
        # Verify bag is deleted
        self.assertFalse(Bag.objects.filter(bag_number='HDK-BAG-TEST100').exists())
        
        # Verify no error messages
        message_list = list(messages)
        error_messages = [m for m in message_list if m.level_tag == 'error']
        self.assertEqual(len(error_messages), 0)
    
    def test_delete_model_with_sealed_bag_shows_error(self):
        """Test that delete_model shows error message for SEALED bags"""
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib import messages as django_messages
        
        # Create a SEALED bag
        bag = Bag.objects.create(bag_number='HDK-BAG-TEST101', status='SEALED')
        
        # Create a mock request
        request = self.factory.post('/admin/exportimport/bag/')
        request.user = self.admin_user
        
        # Add messages framework support
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        # Call delete_model
        self.bag_admin.delete_model(request, bag)
        
        # Verify bag still exists (not deleted)
        self.assertTrue(Bag.objects.filter(bag_number='HDK-BAG-TEST101').exists())
        
        # Verify error message was added
        message_list = list(messages)
        error_messages = [m for m in message_list if m.level_tag == 'error']
        self.assertEqual(len(error_messages), 1)
        self.assertIn('Cannot delete bag with status SEALED', str(error_messages[0]))
    
    def test_delete_model_with_in_manifest_bag_shows_error(self):
        """Test that delete_model shows error message for IN_MANIFEST bags"""
        from django.contrib.messages.storage.fallback import FallbackStorage
        
        # Create an IN_MANIFEST bag
        bag = Bag.objects.create(bag_number='HDK-BAG-TEST102', status='IN_MANIFEST')
        
        # Create a mock request
        request = self.factory.post('/admin/exportimport/bag/')
        request.user = self.admin_user
        
        # Add messages framework support
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        # Call delete_model
        self.bag_admin.delete_model(request, bag)
        
        # Verify bag still exists (not deleted)
        self.assertTrue(Bag.objects.filter(bag_number='HDK-BAG-TEST102').exists())
        
        # Verify error message was added
        message_list = list(messages)
        error_messages = [m for m in message_list if m.level_tag == 'error']
        self.assertEqual(len(error_messages), 1)
        self.assertIn('Cannot delete bag with status IN_MANIFEST', str(error_messages[0]))
    
    def test_delete_model_with_dispatched_bag_shows_error(self):
        """Test that delete_model shows error message for DISPATCHED bags"""
        from django.contrib.messages.storage.fallback import FallbackStorage
        
        # Create a DISPATCHED bag
        bag = Bag.objects.create(bag_number='HDK-BAG-TEST103', status='DISPATCHED')
        
        # Create a mock request
        request = self.factory.post('/admin/exportimport/bag/')
        request.user = self.admin_user
        
        # Add messages framework support
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        
        # Call delete_model
        self.bag_admin.delete_model(request, bag)
        
        # Verify bag still exists (not deleted)
        self.assertTrue(Bag.objects.filter(bag_number='HDK-BAG-TEST103').exists())
        
        # Verify error message was added
        message_list = list(messages)
        error_messages = [m for m in message_list if m.level_tag == 'error']
        self.assertEqual(len(error_messages), 1)
        self.assertIn('Cannot delete bag with status DISPATCHED', str(error_messages[0]))
