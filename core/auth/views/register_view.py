from django.shortcuts import render, redirect
from django.views import View
from core.auth.forms.register_form import RegisterForm
from django.contrib.auth import login
from django.contrib import messages  # Import messages

class RegisterView(View):
    form_class = RegisterForm
    template_name = 'signup/signup.html'

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful! You are now logged in.')
            return redirect('home')  # Replace 'home' with the name of your home page URL pattern
        else:
            # Show an error message if form is not valid
            messages.error(request, 'Registration failed. Please check the form for errors.')
        return render(request, self.template_name, {'form': form})
