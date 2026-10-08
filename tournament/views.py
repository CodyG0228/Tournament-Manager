from django.shortcuts import render


def tournament_list(request):
    return render(request, "tournament/base.html")
