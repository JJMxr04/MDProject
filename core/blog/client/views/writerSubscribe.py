from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from core.blog.writer.models import SubscriptionPlan, Article
from core.user.models import User
from core.user.serializers import WriterSerializer
from core.blog.writer.serializers.subscriptionPlan import SubscriptionPlanSerializer
from core.blog.client.models import Subscription  # Adjust import according to your project's structure
import stripe

@login_required(login_url='/auth/login/')
def writer_subscribe(request, writer_id):
    writer = User.objects.filter(public_id=writer_id).first()
    existing_plan = SubscriptionPlan.objects.filter(writer=writer).first()

    # Check if the user is subscribed to the writer
    is_subscribed = Subscription.objects.filter(subscriber=request.user,writer=writer).exists()

    if is_subscribed:
        # If the user is subscribed, display the articles from the writer
        articles = Article.objects.filter(author=writer, is_published=True).order_by('-date_published')
        context = {
            'articles': articles,
            'writer': writer,
        }
        return render(request, 'portal/blog/client/client-writer-is-subscribed.html', context)

    # If the user is not subscribed, show the subscription page
    writer_ser = WriterSerializer(writer).data
    existing_plan_ser = SubscriptionPlanSerializer(existing_plan).data

    context = {
        'writer': writer_ser,
        'subscription_plan': existing_plan_ser,
    }

    return render(request, 'portal/blog/client/client-writer-subscribe.html', context)
