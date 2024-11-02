from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from core.event.models import Forum, Thread, Post, Reply
from core.event.forms import ThreadForm, PostForm, ReplyForm
from core.event.models import Event
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

@login_required
def create_reply(request, post_id):
    parent_post = get_object_or_404(Post, id=post_id)  # The post to which we are replying
    thread = parent_post.thread
    event = parent_post.event  # The event, if any, associated with this post
    
    if request.method == "POST":
        form = ReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.post = parent_post
            reply.created_by = request.user

            
            try:
                reply.save()
                return redirect("core-portal:upcoming-events-detail", event_id=event.id)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)  # Return JSON error response
        else:
            # If the form is not valid, return the errors
            return JsonResponse({'errors': form.errors}, status=400)

    return JsonResponse({'error': 'Invalid request method.'}, status=405)  # Handle non-POST requests


def thread_detail(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    # You may want to include related posts or other context here
    return render(request, 'portal/event/thread_detail.html', {'thread': thread})


def forum_list(request):
    forums = Forum.objects.all()
    return render(request, "portal/event/forum_list.html", {"forums": forums})

def thread_list(request, forum_id):
    forum = get_object_or_404(Forum, id=forum_id)
    threads = forum.threads.all()
    return render(request, "portal/event/thread_list.html", {"forum": forum, "threads": threads})

@login_required
def create_thread(request, forum_id):
    forum = get_object_or_404(Forum, id=forum_id)
    if request.method == "POST":
        form = ThreadForm(request.POST)
        if form.is_valid():
            thread = form.save(commit=False)
            thread.forum = forum
            thread.created_by = request.user
            thread.save()
            return redirect("core-portal:thread_list", forum_id=forum.id)
    else:
        form = ThreadForm()
    return render(request, "portal/event/create_thread.html", {"form": form, "forum": forum})
@login_required
def create_post(request, thread_id=None, event_id=None):
    thread = get_object_or_404(Thread, id=thread_id) if thread_id else None
    event = get_object_or_404(Event, id=event_id) if event_id else None

    if request.method == "POST":
        form = PostForm(request.POST)
        
        # Print the form data for debugging
        print("Form Data:", request.POST)
        
        if form.is_valid():
            post = form.save(commit=False)
            post.thread = thread
            post.event = event
            post.created_by = request.user
            
            try:
                post.save()
                if thread:
                    return redirect("core-portal:thread_detail", thread_id=thread.id)  # Adjust as necessary
                if event:
                    return redirect("core-portal:upcoming-events-detail", event_id=event.id)  # Use the correct app name
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)  # Return JSON error response
        else:
            # Print form errors to console for debugging
            print("Form Errors:", form.errors)
            return JsonResponse({'errors': form.errors}, status=400)

    return JsonResponse({'error': 'Invalid request method.'}, status=405)  # Handle non-POST requests
