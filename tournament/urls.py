from django.urls import path
from . import views

urlpatterns = [
    path("", views.tournament_list, name="dashboard"),
]