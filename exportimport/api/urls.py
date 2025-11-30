from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShipmentViewSet, BagViewSet, login_view, profile_view

router = DefaultRouter()
router.register(r'shipments', ShipmentViewSet, basename='shipment')
router.register(r'bags', BagViewSet, basename='bag')

urlpatterns = [
    # Authentication
    path('auth/login/', login_view, name='api_login'),
    path('auth/profile/', profile_view, name='api_profile'),
    
    # Router URLs
    path('', include(router.urls)),
]
