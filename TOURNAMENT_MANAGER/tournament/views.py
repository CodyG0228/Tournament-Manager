from django.shortcuts import render



def tournament_list(request):
    return render(request, 'tournament/tournament_list.html', {})
# Create your views here.
