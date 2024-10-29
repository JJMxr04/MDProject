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
            user = form.save(commit=False)
            user.save()  # Save the user object first
            form.save_m2m()  # If your form has ManyToMany fields

            # Pass `request` to `send_activation_email`
            send_activation_email(user, request)  # Pass request here
            login(request, user)
            messages.success(request, 'Registration successful! You are now logged in.')
            return redirect('home')
        else:
            messages.error(request, 'Registration failed. Please check the form for errors.')
        return render(request, self.template_name, {'form': form})
