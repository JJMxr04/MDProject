from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from core.blog.writer.models import SubscriptionPlan
from core.user.models import User
from core.user.serializers import WriterSerializer
from core.blog.writer.serializers.subscriptionPlan import SubscriptionPlanSerializer
import stripe



@login_required(login_url='/auth/login/')
def writer_subscribe(request, writer_id):
    writer = User.objects.filter(public_id=writer_id).first()
    existing_plan = SubscriptionPlan.objects.filter(writer=writer).first()

    writer_ser = WriterSerializer(writer).data
    existing_plan_ser = SubscriptionPlanSerializer(existing_plan).data

    context = {
        'writer': writer_ser,
        'subscription_plan': existing_plan_ser,
        'stripe_publishable_key': settings.STRIPE_PUBLISH_KEY,
    }

    return render(request, 'portal/blog/client/client-writer-subscribe.html', context)
