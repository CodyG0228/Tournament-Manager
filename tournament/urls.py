from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("players/", views.players, name="players"),
    path("tournaments/create/", views.tournament_setup, name="tournament_setup"),
]