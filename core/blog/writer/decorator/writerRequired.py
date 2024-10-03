from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404  # Assuming Article model is defined elsewhere
from core.blog.writer.models import Article

def writer_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_writer and not request.user.is_staff:
            return HttpResponseForbidden("You are not allowed to access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def author_required(view_func):
    def _wrapped_view(request, art_id, *args, **kwargs):  # Added article_id parameter
        article = get_object_or_404(Article, id=art_id)  # Fetch the article
        if article.author != request.user:  # Check if the user is the author
            return HttpResponseForbidden("You are not allowed to access this page.")
        return view_func(request, art_id, *args, **kwargs)  # Pass article_id to the view
    return _wrapped_view