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
    path('parcels/<int:parcel_id>/details/', views.parcel_details, name='parcel_details'),
    path('parcels/<int:parcel_id>/update/', views.update_parcel, name='update_parcel'),
    path('parcels/<int:parcel_id>/delete/', views.delete_parcel, name='delete_parcel'),
    
    # Parcel Booking API (Staff)
    path('api/book-parcel/<int:parcel_id>/', views.book_parcel, name='book_parcel'),
    
    # Pending Parcels (Staff)
    path('pending-parcels/', views.pending_parcels, name='pending_parcels'),
    
    # HAWB View
    path('hawb/<int:shipment_id>/', views.invoice_view, name='hawb_view'),
    
    # Invoice Management (Commercial Invoice)
    path('invoice/<int:shipment_id>/upload/', views.invoice_upload_view, name='invoice_upload'),
    path('invoice/<int:shipment_id>/generate/', views.invoice_generate_view, name='invoice_generate'),
    path('invoice/<int:shipment_id>/delete/', views.invoice_delete_view, name='invoice_delete'),
    path('invoice/<int:shipment_id>/download/', views.invoice_download_view, name='invoice_download'),
    
    # Bag Management (Staff)
    path('bags/', views.bags_view, name='bags'),
    path('bags/create/', views.create_bag, name='create_bag'),
    path('bags/<int:bag_id>/', views.get_bag, name='get_bag'),
    path('bags/<int:bag_id>/detail/', views.bag_detail_view, name='bag_detail'),
    path('bags/<int:bag_id>/add-shipment/', views.add_shipment_to_bag, name='add_shipment_to_bag'),
    path('bags/<int:bag_id>/remove-shipment/<int:shipment_id>/', views.remove_shipment_from_bag, name='remove_shipment_from_bag'),
    path('bags/<int:bag_id>/seal/', views.seal_bag_view, name='seal_bag'),
    path('bags/<int:bag_id>/unseal/', views.unseal_bag_view, name='unseal_bag'),
    path('bags/<int:bag_id>/delete/', views.delete_bag_view, name='delete_bag'),
    path('bags/<int:bag_id>/status/', views.update_bag_status, name='update_bag_status'),
    path('bags/<int:bag_id>/label/', views.print_bag_label, name='print_bag_label'),
    path('bags/clear-context/', views.clear_bag_context, name='clear_bag_context'),
    
    # Manifest Management (BD Manager/Admin only)
    path('manifests/', manifest_views.ManifestListView.as_view(), name='manifests'),
    path('manifests/search/', manifest_views.ManifestSearchByMAWBView.as_view(), name='manifest_search'),
    path('manifests/create/', manifest_views.ManifestCreateView.as_view(), name='manifest_create'),
    path('manifests/<int:pk>/', manifest_views.ManifestDetailView.as_view(), name='manifest_detail'),
    path('manifests/<int:pk>/update/', manifest_views.ManifestUpdateView.as_view(), name='manifest_update'),
    path('manifests/<int:pk>/delete/', manifest_views.ManifestDeleteView.as_view(), name='manifest_delete'),
    path('manifests/<int:pk>/finalize/', manifest_views.ManifestFinalizeView.as_view(), name='manifest_finalize'),
    path('manifests/<int:pk>/status/', manifest_views.ManifestStatusUpdateView.as_view(), name='manifest_status'),
    path('manifests/<int:pk>/export/pdf/', manifest_views.ManifestExportPDFView.as_view(), name='manifest_export_pdf'),
    path('manifests/<int:pk>/export/excel/', manifest_views.ManifestExportExcelView.as_view(), name='manifest_export_excel'),
    path('manifests/<int:manifest_pk>/shipments/<int:shipment_pk>/edit/', manifest_views.ShipmentEditView.as_view(), name='shipment_edit'),
    path('manifests/<int:manifest_pk>/shipments/<int:shipment_pk>/remove/', manifest_views.ShipmentRemoveView.as_view(), name='shipment_remove'),
    
    # Manifest individual shipment management
    path('manifests/<int:pk>/add-shipment/', manifest_views.ManifestAddShipmentView.as_view(), name='manifest_add_shipment'),
    path('manifests/<int:pk>/remove-individual-shipment/<int:shipment_pk>/', manifest_views.ManifestRemoveIndividualShipmentView.as_view(), name='manifest_remove_individual_shipment'),
    path('manifests/<int:pk>/available-shipments/', manifest_views.ManifestAvailableShipmentsView.as_view(), name='manifest_available_shipments'),
    path('manifests/available-shipments-for-new/', manifest_views.AvailableShipmentsForNewManifestView.as_view(), name='available_shipments_for_new_manifest'),
]
