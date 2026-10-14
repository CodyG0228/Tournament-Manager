from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("players/", views.players, name="players"),
    path("players/<int:pk>/delete/", views.delete_player, name="delete_player"),
    path("tournaments/create/", views.tournament_setup, name="tournament_setup"),
    path("tournaments/<int:pk>/", views.tournament_detail, name="tournament_detail"),
    path("tournaments/<int:pk>/register/", views.register_player, name="register_player"),
    path("tournaments/<int:pk>/delete/", views.delete_tournament, name="delete_tournament"),
    path("tournaments/<int:pk>/bracket/generate/", views.generate_bracket, name="generate_bracket"),
    path("tournaments/<int:pk>/bracket/advance/", views.advance_round, name="advance_round"),
    path("registrations/<int:pk>/check-in/", views.toggle_check_in, name="toggle_check_in"),
    path("matches/create/", views.create_match, name="create_match"),
    path("matches/<int:pk>/result/", views.record_result, name="record_result"),
]