import uuid  #this is useful for generating unique player_id values on registration

from django.shortcuts import render, redirect, get_object_or_404
#match and MatchParticipant are needed by create_match, without them caused NameError
from .models import Tournament, Player, Match, MatchParticipant


def dashboard(request):
    #shows the 5 most recent setup tournaments. the template expects 'tournaments'.
    #template path must be namespaced for APP_DIRS
    active_tournaments = Tournament.objects.filter(status='SETUP').order_by('-date')[:5]
    context = {'tournaments': active_tournaments}
    return render(request, "tournament/dashboard.html", context)


def players(request):
    #GET renders the list, POST registers a new player
    #POST handling lives here (not a separate view) because the form posts to /players/
    if request.method == 'POST':
        #stripping blanks and skipping duplicates so usernames stay unique
        username = (request.POST.get('username') or '').strip()
        if username and not Player.objects.filter(username=username).exists():
            try:
                Player.objects.create(
                    username=username,
                    player_id=str(uuid.uuid4())
                )
            except Exception as e:
                print(f"Error registering player: {e}")
        return redirect('players')

    #the GET: list all players for tournament/players.html.
    all_players = Player.objects.all().order_by('username')
    context = {'players': all_players}
    return render(request, "tournament/players.html", context)


def tournament_setup(request):
    #GET shows the form, POST creates a Tournament
    #form fields must be name/game_type/date to match the Tournament model
    if request.method == 'POST':
        try:
            name = (request.POST.get('name') or '').strip()
            game_type = request.POST.get('game_type')
            date = request.POST.get('date') #YYYY-MM-DD string for the DateField

            #without date the DB will raise NOT NULL
            if not name or not date:
                return render(request, "tournament/tournament_setup.html", {})

            #validation using the new models
            Tournament.objects.create(
                name=name,
                game_type=game_type or 'unknown', #default when nothing is selected
                date=date,
                status='SETUP'
            )
            #success returns to the dashboard list
            return redirect('dashboard')

        except Exception as e:
            print(f"Error creating tournament: {e}")
    
    context = {}
    return render(request, "tournament/tournament_setup.html", context)


def create_match(request):
    """
    Creates a Match plus one MatchParticipant per player, mirroring Bracket.py logic.
    Wired at matches/create/; GET shows the form, POST saves.
    """
    if request.method == 'POST':
        try:
            #gathering inputs from match_setup.html
            tournament_id = request.POST.get('tournament_id')
            raw_ids = request.POST.getlist('player_ids') 
            player_ids = []
            for chunk in raw_ids:
                for part in str(chunk).replace(',', '\n').splitlines():
                    part = part.strip()
                    if part:
                        player_ids.append(part)
            round_num = int(request.POST.get('round_num'))

            #load tournament and matching players, error page if IDs match nothing
            tournament = Tournament.objects.get(pk=tournament_id)
            participants_db = Player.objects.filter(player_id__in=player_ids)
            
            if not participants_db:
                return render(request, "tournament/error.html", {"message": "Invalid player IDs provided."})

            #run the same grouping through Bracket.py (validates the heat)
            #Bracket.Match requires max_players/advance_count
            from Bracket import Match as BracketMatch #logic class at root of project
            from Bracket import Player as BracketPlayer #dataclass is a mirror of the Player model

            match_id = f"M{tournament_id}-{round_num}-{len(participants_db)}"
            bracket_match = BracketMatch(
                match_id=match_id,
                round_num=round_num,
                max_players=max(2, len(participants_db)),
                advance_count=1,
            )

            for player in participants_db:
                #converting each DB row to the Bracket dataclass before adding
                bracket_player = BracketPlayer(player_id=player.player_id, username=player.username)
                bracket_match.add_player(bracket_player)

            #creating the Match once avoids duplicate match_id (unique) errors
            db_match = Match.objects.create(tourney=tournament, match_id=match_id, round_number=round_num)
            for player in participants_db:
                MatchParticipant.objects.create(
                    match=db_match,
                    player=player,
                    score=0 #initialize score to 0
                )

            #successful call would return the newly created match object
            return redirect('dashboard')
        
        except Exception as e:
            print(f"Error creating match: {e}")
    
    #render a form for match creation (placeholder view)
    context = {} 
    return render(request, "tournament/match_setup.html", context)


def tournament_detail(request, pk):
    #detail page for tournaments previously the dashboard linked to "#" so it was a dead link
    tournament = get_object_or_404(Tournament, pk=pk)
    #registrations (with player rows), matches (with participant rows), and saved bracket state
    registrations = tournament.registrations.select_related("player").order_by("player__username")
    matches = tournament.matches.prefetch_related("participants__player").order_by("round_number")
    bracket = getattr(tournament, "bracket", None)
    context = {
        "tournament": tournament,
        "registrations": registrations,
        "matches": matches,
        "bracket": bracket,
    }
    return render(request, "tournament/tournament_detail.html", context)