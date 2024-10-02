from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required
from core.event.models import Event, Outcome
from core.blog.writer.forms import ArticleForm
from django.http import HttpResponse, HttpResponseBadRequest

@login_required(login_url='/auth/login/')
@writer_required
def create_article(request):
    form = ArticleForm()

    if request.method == 'POST':
        form = ArticleForm(request.POST)
        event_id = request.POST.get('event_id')
        outcome_id = request.POST.get('outcome_id')  # New line to get outcome_id

        if not event_id or not outcome_id:  # Updated condition to check both IDs
            return HttpResponseBadRequest("Event and Outcome are required.")
        
        try:
            event = Event.objects.get(id=event_id)
            outcome = Outcome.objects.get(id=outcome_id)
        except Event.DoesNotExist:
            form.add_error(None, "The selected event does not exist.")
            return render(request, 'portal/blog/writer/create-article.html', {'CreateArticleForm': form})

        # Add logic to handle outcome_id if necessary
        # Example: outcome = Outcome.objects.get(id=outcome_id)

        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.event = event  # Ensure the event is saved
            article.outcome = outcome  # Uncomment if you handle outcome
            article.save()
            return HttpResponse('Article created!')

    context = {'CreateArticleForm': form}
    return render(request, 'portal/blog/writer/create-article.html', context)
