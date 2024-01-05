
from django.core.mail import send_mail
from django.shortcuts import render
from django.http import HttpResponse

def send_Email(subject,message,from_email,recipient_list):
    # subject = 'Subject Here'
    # message = 'Message Here'
    # from_email = 'your_email@example.com'
    # recipient_list = ['recipient@example.com']

    send_mail(subject, message, from_email, recipient_list)

    return HttpResponse('Email sent successfully!')

