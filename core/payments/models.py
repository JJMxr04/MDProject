from django.db import models
from django.contrib.auth import get_user_model
from core.blog.client.models import Subscription

User = get_user_model()

class Invoice(models.Model):
    STATUS_CHOICES = (
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='invoices')
    stripe_invoice_id = models.CharField(max_length=255, null=True, blank=True)  # Stripe invoice ID
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Store the amount paid/failed
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invoice {self.stripe_invoice_id} - {self.status} - {self.user.email}"

