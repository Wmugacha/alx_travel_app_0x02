from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, status
from rest_framework.views import APIView
from .models import Listing, Booking, Payment
from .serializers import ListingSerializer, BookingSerializer, PaymentSerializer
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from chapa import Chapa
from django.conf import settings
from django.db import transaction
import uuid
from rest_framework.response import Response


class ListingViewSet(viewsets.ModelViewSet):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

chapa = Chapa(settings.CHAPA_SECRET_KEY)

@method_decorator(csrf_exempt, name='dispatch')
class InitiatePaymentView(APIView):
    def post(self, request, *args, **kwargs):
        user = request.user
        data = request.data

        try:
            listing_id = data.get("listing_id")
            check_in = data.get("check_in")
            check_out = data.get("check_out")
            guests = data.get("guests")
            amount = data.get("amount")

            if not all([listing_id, check_in, check_out, guests, amount]):
                return Response({"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)

            listing = get_object_or_404(Listing, id=listing_id)
            tx_ref = f"txn_{uuid.uuid4().hex}"

            with transaction.atomic():
                booking = Booking.objects.create(
                    user=user,
                    listing=listing,
                    check_in=check_in,
                    check_out=check_out,
                    guests=guests,
                    booking_status='pending'
                )        

                chapa_response = chapa.initialize(
                    email=user.email,
                    amount=amount,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    tx_ref=tx_ref,
                    callback_url= "http://localhost:8000/api/"
                )

                transaction_id = chapa_response['data']['id']

                Payment.objects.create(
                    booking=booking,
                    tx_ref=tx_ref,
                    transaction_id=transaction_id,
                    amount=amount,
                    payment_status='pending')

            return Response(chapa_response, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)