from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views import View
from core.auth.forms.register_form import RegisterForm
from django.contrib.auth import login
from django.contrib import messages
from core.auth.models import email  # Import your email sending function
from core.ratelimit import rate_limit

class RegisterView(View):
    form_class = RegisterForm
    template_name = 'signup/signup.html'

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    # Anonymous, sends an activation email, and the waitlist-approval form
    # error makes approval status probeable — brake it (plan §7.5 item 3).
    @method_decorator(rate_limit("auth-register", 5, 3600))
    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            user = form.save()
            email.send_activation_email(user,request)
            messages.success(request, 'Registration successful! You are now logged in.')
            return redirect('core-auth:activation-email')  # Replace 'home' with the name of your home page URL pattern
        else:
            messages.error(request, 'Registration failed. Please correct the errors below.')
            for field, errors in form.errors.items():
                for error in errors:
                    messages.warning(request, f"{field.capitalize()}: {error}")
        return render(request, self.template_name, {'form': form})
