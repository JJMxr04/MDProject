from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.blog.writer.models import Article
from core.blog.client.models import Subscription  # Adjust import according to your project's structure
from core.user.models import User
from core.user.serializers import WriterSerializer
from core.blog.writer.models import SubscriptionPlan
from core.blog.writer.serializers.subscriptionPlan import SubscriptionPlanSerializer

@login_required(login_url='/auth/login/')
def writer_subscribe(request,writer_id):
    print(writer_id)

    writer = User.objects.filter(public_id=writer_id).first()
    existing_plan = SubscriptionPlan.objects.filter(writer=writer).first()
    writer_ser = WriterSerializer(writer).data 
    existing_plan_ser = SubscriptionPlanSerializer(existing_plan).data
    # # Get all active subscriptions of the current user
    context={'writer':writer_ser,
             "subscription_plan":existing_plan_ser}
    # context={'writer':{}}
    
    return render(request, 'portal/blog/client/client-writer-subscribe.html',context)
