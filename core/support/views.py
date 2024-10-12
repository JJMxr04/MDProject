from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Ticket, Comment
from .forms import TicketForm, CommentForm

from django.contrib.admin.views.decorators import staff_member_required
@staff_member_required
def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user
            ticket.save()
            return redirect('ticket_list')
    else:
        form = TicketForm()
    return render(request, 'admin/support/create_ticket.html', {'form': form})

@staff_member_required
def ticket_list(request):
    tickets = Ticket.objects.all()
    return render(request, 'admin/support/ticket_list.html', {'tickets': tickets})

@staff_member_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    comments = ticket.comments.all()
    if request.method == 'POST':
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.user = request.user
            comment.ticket = ticket
            comment.save()
            return redirect('ticket_detail', ticket_id=ticket.id)
    else:
        comment_form = CommentForm()
    return render(request, 'admin/support/ticket_detail.html', {
        'ticket': ticket, 'comments': comments, 'comment_form': comment_form
    })