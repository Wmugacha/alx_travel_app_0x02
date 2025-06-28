from django.shortcuts import render
from rest_framework import viewsets
from django.views import APIView
from .models import Listing, Booking, Payment
from .serializers import ListingSerializer, BookingSerializer, PaymentSerializer
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from chapa import Chapa
from django.conf import settings
from django.db import transaction
import uuid


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
        amount = request.data.get('amount')
        email = request.data.get('email')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')

        if not amount or not email:
            return JsonResponse(
                {"Error": "Amount is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        tx_ref = f"txn_{uuid.uuid4().hex}"

        response = chapa.initialize(
            email=email,
            amount=amount,
            first_name=first_name,
            last_name=last_name,
            tx_ref=tx_ref,
            callback_url="https://yourcallback.url/here"
        )

        Payment.objects.create(email=email, amount=amount, tx_ref=tx_ref, first_name=first_name, last_name=last_name)

        return JsonResponse(response)