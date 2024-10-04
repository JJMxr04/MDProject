from django.db import models
import uuid


class Tag(models.Model):
    
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name