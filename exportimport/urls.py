from django.urls import path
from . import views
from . import manifest_views

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Customer Registration and Profile
    path('register/', views.CustomerRegistrationView.as_view(), name='customer_register'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('change-password/', views.PasswordChangeView.as_view(), name='change_password'),
    
    # Scanning Interface (Staff)
    path('', views.scan_home, name='scan_home'),
    path('scan/<str:awb>/', views.scan_shipment, name='scan_shipment'),
    path('update/<int:shipment_id>/', views.update_shipment_status, name='update_shipment_status'),
    path('delivery-proof/<int:shipment_id>/', views.create_delivery_proof, name='create_delivery_proof'),
    
    # All Shipments (Staff)
    path('shipments/', views.all_shipments, name='all_shipments'),
    
    # Parcel Booking (Non-Staff)
    path('parcels/', views.parcel_booking, name='parcel_booking'),
    path('parcels/create/', views.create_parcel, name='create_parcel'),
    path('parcels/<int:parcel_id>/', views.get_parcel, name='get_parcel'),
    path('parcels/<int:parcel_id>/update/', views.update_parcel, name='update_parcel'),
    path('parcels/<int:parcel_id>/delete/', views.delete_parcel, name='delete_parcel'),
    
    # Bag Management (Staff)
    path('bags/', views.bags_view, name='bags'),
    path('bags/create/', views.create_bag, name='create_bag'),
    path('bags/<int:bag_id>/', views.get_bag, name='get_bag'),
    path('bags/<int:bag_id>/status/', views.update_bag_status, name='update_bag_status'),
    
    # Manifest Management (BD Manager/Admin only)
    path('manifests/', manifest_views.ManifestListView.as_view(), name='manifests'),
    path('manifests/create/', manifest_views.ManifestCreateView.as_view(), name='manifest_create'),
    path('manifests/<int:pk>/', manifest_views.ManifestDetailView.as_view(), name='manifest_detail'),
    path('manifests/<int:pk>/update/', manifest_views.ManifestUpdateView.as_view(), name='manifest_update'),
    path('manifests/<int:pk>/delete/', manifest_views.ManifestDeleteView.as_view(), name='manifest_delete'),
    path('manifests/<int:pk>/finalize/', manifest_views.ManifestFinalizeView.as_view(), name='manifest_finalize'),
    path('manifests/<int:pk>/status/', manifest_views.ManifestStatusUpdateView.as_view(), name='manifest_status'),
]
