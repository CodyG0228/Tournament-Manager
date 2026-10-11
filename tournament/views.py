from django.shortcuts import render


def dashboard(request):
    return render(request, "tournament/dashboard.html")


def players(request):
    return render(request, "tournament/players.html")


def tournament_setup(request):
    return render(request, "tournament/tournament_setup.html")
