from django.shortcuts import render, redirect
from django.views import View
from core.auth.forms.register_form import RegisterForm
from django.contrib.auth import login

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
            return redirect('home')  # Replace 'home' with the name of your home page URL pattern
        return render(request, self.template_name, {'form': form})




