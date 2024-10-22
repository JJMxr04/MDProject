from django.conf import settings
from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta 
from django.conf import settings
# import stripe
# import os
# stripe.api_key = settings.STRIPE_API_KEY
# stripe.api_version = '2023-10-16' # For exact month handling

class SubscriptionPlanManager(models.Manager):
    pass


# Subscription Plan model for writers to set their subscription rate
class SubscriptionPlan(models.Model):
    writer = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='subscription_plan', 
        limit_choices_to={'is_writer': True}
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Set the monthly price for the subscription')
    objects = SubscriptionPlanManager()

    def __str__(self):
        return f'${self.price}/month to {self.writer.username} '

