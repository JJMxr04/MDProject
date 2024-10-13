from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Ticket, Comment
from .forms import TicketForm, CommentForm

from django.contrib.admin.views.decorators import staff_member_required

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Ticket, Status, Comment
from django.http import JsonResponse
from .models import Status
import json

@staff_member_required
def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user
            ticket.save()
            return redirect('core-admin:ticket_list')
    else:
        form = TicketForm()
    return render(request, 'admin/support/create-ticket.html', {'form': form})

@staff_member_required
def ticket_list(request):
    tickets = Ticket.objects.all()
    statuses = Status.objects.all()
    return render(request, 'admin/support/ticket-list.html', {'tickets': tickets, 'statuses': statuses})

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
    return render(request, 'admin/support/ticket-detail.html', {
        'ticket': ticket, 'comments': comments, 'comment_form': comment_form
    })

# views.py


@staff_member_required
@csrf_exempt
def update_ticket_status(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        ticket_id = data.get('ticket_id')
        status_id = data.get('status_id')

        try:
            ticket = Ticket.objects.get(id=ticket_id)
            new_status = Status.objects.get(id=status_id)
            ticket.status = new_status
            ticket.save()
            return JsonResponse({'success': True})
        except (Ticket.DoesNotExist, Status.DoesNotExist):
            return JsonResponse({'success': False, 'error': 'Invalid data'}, status=400)

    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@staff_member_required
@csrf_exempt
def update_status_order(request):
    if request.method == 'POST':
        try:
            status_order = json.loads(request.body).get('status_order', [])
            for item in status_order:
                status_id = item['id']
                position = item['position']
                status = Status.objects.get(id=status_id)
                status.position = position
                status.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

