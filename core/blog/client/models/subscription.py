from django.conf import settings
from django.db import models
from django.utils import timezone

from django.db import models
from django.utils import timezone
from core.blog.writer.models import SubscriptionPlan





# Updated Subscription Manager
class SubscriptionManager(models.Manager):
    def is_subscribed(self, subscriber, writer):
        """Check if a user is actively subscribed to a writer."""
        return self.filter(subscriber=subscriber, writer=writer, active=True, end_date__gt=timezone.now()).exists()

    def active_subscriptions(self, user):
        """Return all active subscriptions for a user."""
        return self.filter(subscriber=user, active=True, end_date__gt=timezone.now())

    def subscribe(self, subscriber, writer):
        """Subscribe a user to a writer if not already subscribed."""
        plan = SubscriptionPlan.objects.get(writer=writer)
        subscription, created = self.get_or_create(subscriber=subscriber, writer=writer, defaults={'plan': plan})
        if not created:
            subscription.active = True
            subscription.start_date = timezone.now()
            subscription.end_date = subscription.start_date + relativedelta(months=1)
            subscription.save()
        return subscription

    def unsubscribe(self, subscriber, writer):
        """Unsubscribe a user from a writer."""
        subscription = self.filter(subscriber=subscriber, writer=writer).first()
        if subscription:
            subscription.active = False
            subscription.save()

class Subscription(models.Model):
    subscriber = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    writer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscribers', limit_choices_to={'is_writer': True})
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)  # Optional end date for the subscription
    active = models.BooleanField(default=True)

    objects = SubscriptionManager()

    class Meta:
        unique_together = ('subscriber', 'writer')  # Prevent multiple subscriptions to the same writer

    def save(self, *args, **kwargs):
        if not self.end_date:
            # Set the end date to exactly one month after the start date
            self.end_date = self.start_date + relativedelta(months=1)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.subscriber} subscribes to {self.writer}'

    @property
    def is_active(self):
        """Check if the subscription is still active."""
        return self.active and self.end_date > timezone.now()

