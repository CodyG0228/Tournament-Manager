from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),  #homepage
    path("players/", views.players, name="players"),  #list and registration form
    path("tournaments/create/", views.tournament_setup, name="tournament_setup"),  #tournament form
    path("tournaments/<int:pk>/", views.tournament_detail, name="tournament_detail"),  #detail page for View Details links
    path("matches/create/", views.create_match, name="create_match"),  #match form that was not previously wired
]