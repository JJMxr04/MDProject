from django.conf import settings
from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta  # For exact month handling


# Subscription Plan model for writers to set their subscription rate
class SubscriptionPlan(models.Model):
    writer = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='subscription_plan', 
        limit_choices_to={'is_writer': True}
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Set the monthly price for the subscription')

    def __str__(self):
        return f'${self.price}/month to {self.writer} '

