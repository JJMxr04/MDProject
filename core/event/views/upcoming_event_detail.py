import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseNotFound
from django.contrib.auth.decorators import login_required
from core.event.forms import PostForm, ReplyForm
from core.event.models import Event, Post, Reply
from core.event.serializers.event import EventBookmakerSerializer

logger = logging.getLogger(__name__)

@login_required(login_url='/auth/login/')
def upcoming_event_detail(request, event_id):
    # Check if event_id is None and log an error
    if event_id is None:
        logger.error("Received None as event_id.")
        return HttpResponseNotFound("Invalid event ID")

    # Attempt to retrieve the event or log an error if not found
    try:
        event = get_object_or_404(Event, pk=event_id)
    except Event.DoesNotExist:
        logger.error(f"Event with ID {event_id} does not exist.")
        return HttpResponseNotFound("Event not found")

    # Serialize the event data for the template
    try:
        event_data = EventBookmakerSerializer(event).data
    except Exception as e:
        logger.error(f"Error serializing event data for ID {event_id}: {str(e)}")
        return HttpResponseNotFound("Error processing event data")

    # Retrieve all posts associated with this event
    event_posts = Post.objects.filter(event=event)

    # Initialize the PostForm and ReplyForm
    post_form = PostForm(initial={'event': event.id})
    reply_form = ReplyForm()  # Initialize an empty ReplyForm

    # Add the event data and associated posts to the context for rendering
    context = {
        'event': event_data,
        'event_posts': event_posts,
        'post_form': post_form,
        'reply_form': reply_form,  # Include reply_form in the context
    }

    return render(request, 'portal/event/upcoming_event_detail.html', context)
