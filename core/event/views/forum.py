from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from core.event.models import Forum, Thread, Post
from core.event.forms import ThreadForm, PostForm
from core.event.models import Event

# def forum_list(request):
#     forums = Forum.objects.all()
#     return render(request, "forum/forum_list.html", {"forums": forums})

# def thread_list(request, forum_id):
#     forum = get_object_or_404(Forum, id=forum_id)
#     threads = forum.threads.all()
#     return render(request, "forum/thread_list.html", {"forum": forum, "threads": threads})

# @login_required
# def create_thread(request, forum_id):
#     forum = get_object_or_404(Forum, id=forum_id)
#     if request.method == "POST":
#         form = ThreadForm(request.POST)
#         if form.is_valid():
#             thread = form.save(commit=False)
#             thread.forum = forum
#             thread.created_by = request.user
#             thread.save()
#             return redirect("thread_list", forum_id=forum.id)
#     else:
#         form = ThreadForm()
#     return render(request, "forum/create_thread.html", {"form": form, "forum": forum})

@login_required
def create_post(request, thread_id=None, event_id=None):
    thread = get_object_or_404(Thread, id=thread_id) if thread_id else None
    event = get_object_or_404(Event, id=event_id) if event_id else None
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.thread = thread
            post.event = event
            post.created_by = request.user
            post.save()
            if thread:
                return redirect("thread_detail", thread_id=thread.id)  # Adjust as necessary
            if event:
                return redirect("core-portal:upcoming-events-detail", event_id=event.id)  # Use the correct app name
    else:
        form = PostForm(initial={'thread': thread, 'event': event})
    return render(request, "forum/create_post.html", {"form": form, "thread": thread, "event": event})
