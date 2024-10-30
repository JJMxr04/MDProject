from django.shortcuts import render, redirect
from django.views import View
from core.auth.forms.register_form import RegisterForm
from django.contrib.auth import login
from django.contrib import messages

class RegisterView(View):
    form_class = RegisterForm
    template_name = 'signup/signup.html'

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            user = form.save(request=request)
            login(request, user)
            messages.success(request, 'Registration successful! You are now logged in.')
            return redirect('core-portal:portal-dashboard')  # Replace 'home' with the name of your home page URL pattern
        else:
            messages.error(request, 'Registration failed. Please correct the errors below.')
            for field, errors in form.errors.items():
                for error in errors:
                    messages.warning(request, f"{field.capitalize()}: {error}")
        return render(request, self.template_name, {'form': form})
