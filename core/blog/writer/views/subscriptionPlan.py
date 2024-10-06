from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required
from core.blog.writer.models import SubscriptionPlan
from core.blog.writer.forms import SubscriptionPlanForm
from django.http import HttpResponse, HttpResponseBadRequest
from core.blog.writer.serializers.subscriptionPlan import SubscriptionPlanSerializer

@login_required(login_url='/auth/login/')
@writer_required
def subscription_plan(request):
    form = SubscriptionPlanForm()

    # Check for existing subscription plans by the writer
    existing_plan = SubscriptionPlan.objects.filter(writer=request.user).first()  # New line to find existing plan

    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST)
        
        if form.is_valid():
            if existing_plan:
                # Update the existing subscription plan
                existing_plan = form.save(commit=False)  # Create an instance without saving to the database
                existing_plan.writer = request.user  # Ensure the writer is set
                existing_plan.save()  # Save the updated plan
            else:
                # Create a new subscription plan
                new_plan = form.save(commit=False)  # Create an instance without saving to the database
                new_plan.writer = request.user  # Set the writer
                new_plan.save()  # Save the new plan

            return redirect('core-portal:writer-subscription-plan') 
        

    existing_plan_ser = SubscriptionPlanSerializer(existing_plan).data
    context = {'SubscriptionPlanForm': form, 'existing_plan': existing_plan_ser}  # Changed to 'existing_plan'
    print(context) # Include existing_plan in context
    return render(request, 'portal/blog/writer/subscription-plan.html', context)
