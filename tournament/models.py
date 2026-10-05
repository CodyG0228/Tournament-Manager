from django.conf import settings
from django.db import models
from django.utils import timezone

class Tournament(models.Model):
    name = models.CharField(max_length=200) 
    game = models.CharField(max_length=200)
    date = models.DateField()
    status = models.CharField(max_length=50)

    
    def __str__(self):
        return self.name