from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from backend.models import Order


@shared_task
def send_confirmation_email_task(email, token_key):
    send_mail(
        "Confirm registration",
        f"Confirmation token: {token_key}",
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )


@shared_task
def send_order_emails_task(order_id):
    order = Order.objects.select_related("user").get(pk=order_id)
    send_mail(
        "Order accepted",
        f"Order #{order.id} accepted. Total: {order.total_sum}",
        settings.DEFAULT_FROM_EMAIL,
        [order.user.email],
    )
    send_mail(
        "New order",
        f"Order #{order.id} needs processing. Total: {order.total_sum}",
        settings.DEFAULT_FROM_EMAIL,
        [settings.ADMIN_EMAIL],
    )
