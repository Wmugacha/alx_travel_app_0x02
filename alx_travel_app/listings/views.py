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
from .tasks import send_payment_confirmation_email
from django.contrib.auth import get_user_model

User = get_user_model()


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
        user = User.objects.first() #For testing purposes
        #user = request.user
        data = request.data

        try:
            listing_id = data.get("listing_id")
            check_in = data.get("check_in")
            check_out = data.get("check_out")
            guests = data.get("guests")
            amount = data.get("amount")
            phone_number = data.get("phone_number")

            if not all([listing_id, check_in, check_out, guests, amount, phone_number]):
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

                email = "testuser@gmail.com" #For testing Only

                chapa_response = chapa.initialize(
                    email=email,
                    amount=amount,
                    currency='ETB',
                    first_name=user.first_name,
                    last_name=user.last_name,
                    tx_ref=tx_ref,
                    callback_url= "http://localhost:8000/api/"
                )

                if not chapa_response or 'data' not in chapa_response:
                    return Response({"error": "Failed to initialize payment with Chapa"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                print("Chapa response:", chapa_response)

                transaction_id = chapa_response['data'].get('id', tx_ref)

                Payment.objects.create(
                    booking=booking,
                    tx_ref=tx_ref,
                    phone_number=phone_number,
                    transaction_id=transaction_id,
                    amount=amount,
                    currency='ETB',
                    payment_status='pending')

            return Response({
                "checkout_urls" : chapa_response['data']['checkout_url'],
                "tx_ref" : tx_ref
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyPaymentView(APIView):
    def get(self, request, *args, **kwargs):
        print("===== VerifyPaymentView called =====")

        tx_ref = request.query_params.get("tx_ref")

        if not tx_ref:
            return Response({"error": "ref_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(tx_ref=tx_ref)
            
            chapa_response = chapa.verify(tx_ref)
            chapa_status = chapa_response["data"]["status"]

            payment.payment_status = chapa_status
            payment.save()

            #Update Booking
            if chapa_status == "success":
                print("Chapa payment was successful.")
                payment.booking.booking_status = "confirmed"
                payment.booking.save()

                print("Verifying chapa status:", chapa_status)
                print("Triggering Celery email task...")

                send_payment_confirmation_email.delay(
                    user_email=payment.booking.user.email,
                    listing_title=payment.booking.listing.title
                )

            return Response({
                "message": "Payment verified.",
                "status": chapa_status,
                "checkout_url": chapa_response["data"].get("checkout_url"),
                "paid_at": chapa_response["data"].get("created_at"),
                "tx_ref": chapa_response["data"].get("tx_ref")
            }, status=status.HTTP_200_OK)

        except Payment.DoesNotExist:
            return Response({"error": "Payment with that ref_id not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)