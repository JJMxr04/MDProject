# from django.db import models
# from core.user.models import User
# from core.event.models.event import Event
# from django.utils import timezone


# class Tag(models.Model):
#     name = models.CharField(max_length=50, unique=True)

#     def __str__(self):
#         return self.name


# class Article(models.Model):
#     title = models.CharField(max_length=200)
#     slug = models.SlugField(max_length=200, unique=True)
#     author = models.ForeignKey(User, on_delete=models.CASCADE)
#     event = models.ForeignKey(Event, on_delete=models.CASCADE)
#     content = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     published_at = models.DateTimeField(default=timezone.now)
#     tags = models.ManyToManyField(Tag, related_name='articles')
#     is_published = models.BooleanField(default=False)
#     image = models.ImageField(upload_to='articles/', blank=True, null=True)
#     highlight_link = models.CharField(max_length=500)

#     def __str__(self):
#         return self.title

#     class Meta:
#         ordering = ['-published_at']
