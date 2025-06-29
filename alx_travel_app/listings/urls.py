from django.urls import path, include
from rest_framework import routers
from .views import ListingViewSet, BookingViewSet, VerifyPaymentView, InitiatePaymentView

router = routers.DefaultRouter()
router.register(r'listings', ListingViewSet, basename='listing')
router.register(r'bookings', BookingViewSet, basename='booking')

urlpatterns = [
    path('', include(router.urls)),
    path('initiate-payment/', InitiatePaymentView.as_view(), name='initiate_payment'),
    path('verify-payment/', VerifyPaymentView.as_view(), name='verify_payment'),
]