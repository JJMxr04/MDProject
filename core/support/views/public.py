from django.shortcuts import render
from django.shortcuts import render, redirect
from core.support.forms import ContactUsForm

def contact_us(request):
    if request.method == 'POST':
        form = ContactUsForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user  # Assuming user is logged in
            ticket.status_id = 1  # Default to 'Open'
            ticket.save()
            return redirect(' core-web:thank-you')  # Redirect to a thank you page after submission
    else:
        form = ContactUsForm()

    return render(request, 'public/support/contact-us.html', {'form': form})

def thank_you(request):


    return render(request, 'public/support/thank-you.html')