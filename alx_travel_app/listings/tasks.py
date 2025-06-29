from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_payment_confirmation_email(user_email, listing_title):
    print(f"Sending confirmation email to {user_email} for {listing_title}")
    subject = "Your Booking is Confirmed"
    message = f"Hi, your booking for {listing_title} has been confirmed. \nThank you for your payment."
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user_email]

    send_mail(subject, message, from_email, recipient_list)