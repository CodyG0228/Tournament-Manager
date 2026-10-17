from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    #dashboard
    path("", views.dashboard, name="dashboard"),
    #authentication\
    path("signup/",views.signup, name="signup"),
    path("login/", 
         auth_views.LoginView.as_view(
            template_name="registration/login.html" 
         ),
         name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    #players
    path("players/", views.players, name="players"),

    path("players/<int:pk>/delete/", views.delete_player, name="delete_player"),

    path("tournaments/create/", views.tournament_setup, name="tournament_setup"),

    path("tournaments/<int:pk>/", views.tournament_detail, name="tournament_detail"),

    path("tournaments/<int:pk>/register/", views.register_player, name="register_player"),

    path("tournaments/<int:pk>/delete/", views.delete_tournament, name="delete_tournament"),

    #Brackets
    path("tournaments/<int:pk>/bracket/generate/", views.generate_bracket, name="generate_bracket"),

    path("tournaments/<int:pk>/bracket/advance/", views.advance_round, name="advance_round"),

    #existing match routes
    path("registrations/<int:pk>/check-in/", views.toggle_check_in, name="toggle_check_in"),
    path("matches/create/", views.create_match, name="create_match"),
    path("matches/<int:pk>/result/", views.record_result, name="record_result"),
]