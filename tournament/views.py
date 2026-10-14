import uuid

from django.db import transaction
from django.db.models import Count, Max, ProtectedError
from django.shortcuts import render, redirect, get_object_or_404

# the bracket engine lives at the project root (Bracket.py).
# its Match/Player are renamed so they don't clash with the Django models.
from Bracket import BracketPageManager, Match as BracketMatch, Player as BracketPlayer

from .models import (
    Tournament,
    Player,
    Match,
    MatchParticipant,
    TournamentRegistration,
    TournamentBracket,
)


# ---------- bracket helpers ----------

class CheckedInBracketManager(BracketPageManager):
    # same engine as Bracket.py, but only checked-in players go into the bracket
    def fetch_registered_players_from_system(self):
        registrations = TournamentRegistration.objects.filter(
            tournament_id=self.tournament_id,
            checked_in=True,
        ).select_related("player")

        return [
            BracketPlayer(
                player_id=str(reg.player.player_id or reg.player.id),
                username=reg.player.username,
            )
            for reg in registrations
        ]


def _save_round_to_db(tournament, round_matches):
    # writes one round of Bracket.py matches into the Match / MatchParticipant tables.
    # match_id is unique across the whole database, so it is prefixed with the tournament.
    players_by_id = {str(p.player_id or p.id): p for p in Player.objects.all()}

    for bracket_match in round_matches:
        db_match = Match.objects.create(
            tourney=tournament,
            match_id=f"T{tournament.pk}-{bracket_match.match_id}",
            round_number=bracket_match.round_num,
            is_bye=bracket_match.is_bye,
        )

        for part in bracket_match.participants:
            player = players_by_id.get(part.player.player_id)
            if player:
                MatchParticipant.objects.create(
                    match=db_match,
                    player=player,
                    score=part.score,
                    rank=part.rank,
                )


def _load_manager(tournament):
    # rebuilds the in-memory Bracket.py state from this tournament's match rows
    manager = CheckedInBracketManager(tournament.pk)

    db_matches = tournament.matches.prefetch_related(
        "participants__player"
    ).order_by("round_number", "id")

    by_round = {}
    for db_match in db_matches:
        by_round.setdefault(db_match.round_number, []).append(db_match)

    for round_num, round_matches in by_round.items():
        # a single match after round 1 is a final: only the winner advances
        later_single = round_num > 1 and len(round_matches) == 1
        manager.rounds[round_num] = []

        for db_match in round_matches:
            parts = sorted(
                db_match.participants.all(),
                key=lambda p: (p.rank is None, p.rank or 0, p.id),
            )

            if db_match.is_bye:
                advance_count = max(1, len(parts))
            elif later_single:
                advance_count = 1
            else:
                advance_count = manager.advance_per_heat

            bracket_match = BracketMatch(
                match_id=db_match.match_id,
                round_num=round_num,
                max_players=max(2, len(parts)),
                advance_count=advance_count,
                is_bye=db_match.is_bye,
            )

            for part in parts:
                bracket_match.add_player(
                    BracketPlayer(
                        player_id=str(part.player.player_id or part.player.id),
                        username=part.player.username,
                    )
                )

            for bracket_part, part in zip(bracket_match.participants, parts):
                bracket_part.score = part.score
                bracket_part.rank = part.rank

            bracket_match.is_completed = db_match.is_bye or all(
                p.rank is not None for p in parts
            )

            manager.rounds[round_num].append(bracket_match)

    return manager


def _to_int(value, default, minimum=1):
    # turns form text into a whole number, falls back to the default if it isn't one
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, number)


# ---------- views ----------

def dashboard(request):
    active_tournaments = Tournament.objects.filter(
        status='SETUP'
    ).annotate(
        entrant_count=Count('registrations')
    ).order_by('-date')[:5]

    tournament_count = Tournament.objects.count()

    player_count = Player.objects.count()

    match_count = Match.objects.count()

    context = {
        'tournaments': active_tournaments,
        'tournament_count': tournament_count,
        'player_count': player_count,
        'match_count': match_count,
    }

    return render(
        request,
        "tournament/dashboard.html",
        context
    )


def players(request):
    if request.method == 'POST':
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

    all_players = Player.objects.all().order_by('username')

    context = {
        'players': all_players
    }

    return render(request, "tournament/players.html", context)


def tournament_setup(request):
    if request.method == 'POST':
        try:
            name = (request.POST.get('name') or '').strip()
            game_type = request.POST.get('game_type')
            date = request.POST.get('date')

            valid_formats = [choice[0] for choice in Tournament.FORMAT_CHOICES]
            tournament_format = request.POST.get('format')
            if tournament_format not in valid_formats:
                tournament_format = 'single_elimination'

            num_rounds = _to_int(request.POST.get('num_rounds'), 3)
            max_players = _to_int(request.POST.get('max_players'), 16, minimum=2)

            if not name or not date:
                return render(
                    request,
                    "tournament/tournament_setup.html",
                    {}
                )

            Tournament.objects.create(
                name=name,
                game_type=game_type or 'unknown',
                date=date,
                status='SETUP',
                format=tournament_format,
                num_rounds=num_rounds,
                max_players=max_players,
            )

            return redirect('dashboard')

        except Exception as e:
            print(f"Error creating tournament: {e}")

    return render(
        request,
        "tournament/tournament_setup.html",
        {}
    )


def create_match(request):
    if request.method == 'POST':
        try:
            tournament_id = request.POST.get('tournament_id')

            raw_ids = request.POST.getlist('player_ids')

            player_ids = []

            for chunk in raw_ids:
                for part in str(chunk).replace(',', '\n').splitlines():
                    part = part.strip()

                    if part:
                        player_ids.append(part)

            round_num = int(request.POST.get('round_num'))

            tournament = Tournament.objects.get(pk=tournament_id)

            participants_db = Player.objects.filter(
                player_id__in=player_ids
            )

            if not participants_db:
                return render(
                    request,
                    "tournament/error.html",
                    {"message": "Select at least one player for the match."}
                )

            # number the matches within the round so several matches can share a round
            existing = Match.objects.filter(
                tourney=tournament,
                round_number=round_num
            ).count()
            match_id = f"M{tournament_id}-{round_num}-{existing + 1}"

            bracket_match = BracketMatch(
                match_id=match_id,
                round_num=round_num,
                max_players=max(2, len(participants_db)),
                advance_count=1,
            )

            for player in participants_db:
                bracket_player = BracketPlayer(
                    player_id=player.player_id,
                    username=player.username
                )

                bracket_match.add_player(bracket_player)

            db_match = Match.objects.create(
                tourney=tournament,
                match_id=match_id,
                round_number=round_num
            )

            for player in participants_db:
                MatchParticipant.objects.create(
                    match=db_match,
                    player=player,
                    score=0
                )

            # go back to the tournament page so the new match is visible
            return redirect('tournament_detail', pk=tournament.pk)

        except Exception as e:
            print(f"Error creating match: {e}")

    # GET (or a failed POST): show the form for the tournament in ?tournament=<id>
    # only checked-in players can be put into a match
    tournament = None
    registrations = []

    tournament_id = request.GET.get('tournament') or request.POST.get('tournament_id')

    if tournament_id:
        tournament = Tournament.objects.filter(pk=tournament_id).first()

        if tournament:
            registrations = tournament.registrations.filter(
                checked_in=True
            ).select_related(
                "player"
            ).order_by("player__username")

    context = {
        "tournament": tournament,
        "registrations": registrations,
    }

    return render(
        request,
        "tournament/match_setup.html",
        context
    )


def tournament_detail(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)

    registrations = tournament.registrations.select_related(
        "player"
    ).order_by("player__username")

    matches = list(
        tournament.matches.prefetch_related(
            "participants__player"
        ).order_by("round_number", "id")
    )

    # work out each match's status and winner(s) for the template
    for match in matches:
        participants = list(match.participants.all())
        match.reported = any(p.rank is not None for p in participants)
        match.winners = ", ".join(
            p.player.username for p in participants if p.rank == 1
        )

    bracket = getattr(tournament, "bracket", None)

    registration_count = registrations.count()
    checked_in_count = registrations.filter(checked_in=True).count()
    is_full = registration_count >= tournament.max_players

    # where the bracket is up to
    current_round = max((m.round_number for m in matches), default=0)
    current_matches = [m for m in matches if m.round_number == current_round]
    round_complete = bool(current_matches) and all(m.reported for m in current_matches)
    tournament_finished = bool(bracket) and round_complete and len(current_matches) == 1
    can_advance = bool(bracket) and round_complete and not tournament_finished
    can_generate = not matches and checked_in_count >= 2
    champion = current_matches[0].winners if tournament_finished else ""

    # standings saved by Bracket.py
    leaderboard = []
    if bracket and bracket.bracket_data:
        leaderboard = bracket.bracket_data.get("leaderboard", [])

    # players not yet registered for this tournament (fills the dropdown)
    available_players = Player.objects.exclude(
        tournamentregistration__tournament=tournament
    ).order_by("username")

    context = {
        "tournament": tournament,
        "registrations": registrations,
        "registration_count": registration_count,
        "checked_in_count": checked_in_count,
        "is_full": is_full,
        "matches": matches,
        "current_round": current_round,
        "tournament_finished": tournament_finished,
        "can_advance": can_advance,
        "can_generate": can_generate,
        "champion": champion,
        "leaderboard": leaderboard,
        "bracket": bracket,
        "available_players": available_players,
    }

    return render(
        request,
        "tournament/tournament_detail.html",
        context
    )


def register_player(request, pk):
    # POST only: attaches a player to a tournament.
    # get_or_create respects the unique (tournament, player) pair.
    tournament = get_object_or_404(Tournament, pk=pk)

    if request.method == 'POST':
        # stop adding once the tournament is at its player limit
        if tournament.registrations.count() >= tournament.max_players:
            return redirect('tournament_detail', pk=pk)

        player_pk = request.POST.get('player')

        if player_pk:
            player = get_object_or_404(Player, pk=player_pk)

            TournamentRegistration.objects.get_or_create(
                tournament=tournament,
                player=player
            )

    return redirect('tournament_detail', pk=pk)


def toggle_check_in(request, pk):
    # POST only: flips a registration between checked in and not checked in
    registration = get_object_or_404(TournamentRegistration, pk=pk)

    if request.method == 'POST':
        registration.checked_in = not registration.checked_in
        registration.save()

    return redirect('tournament_detail', pk=registration.tournament_id)


def generate_bracket(request, pk):
    # POST only: builds round 1 (shuffled seeding plus byes) from the checked-in players
    tournament = get_object_or_404(Tournament, pk=pk)

    if request.method == 'POST' and not tournament.matches.exists():
        checked_in = tournament.registrations.filter(checked_in=True).count()

        if checked_in < 2:
            return render(
                request,
                "tournament/error.html",
                {"message": "Check in at least 2 players before generating the bracket."}
            )

        with transaction.atomic():
            manager = CheckedInBracketManager(tournament.pk)
            rounds = manager.generate_bracket()
            _save_round_to_db(tournament, rounds[1])

    return redirect('tournament_detail', pk=pk)


def advance_round(request, pk):
    # POST only: once every match in the round is reported, builds the next round
    tournament = get_object_or_404(Tournament, pk=pk)
    has_bracket = TournamentBracket.objects.filter(tournament=tournament).exists()

    if request.method == 'POST' and has_bracket:
        with transaction.atomic():
            manager = _load_manager(tournament)

            if manager.rounds:
                current_round = max(manager.rounds.keys())
                next_matches = manager.advance_to_next_round(current_round)

                # None means the round isn't finished yet, or the tournament is over
                if next_matches:
                    _save_round_to_db(tournament, next_matches)

    return redirect('tournament_detail', pk=pk)


@transaction.atomic
def record_result(request, pk):
    # POST only: saves the scores, ranks the players and credits wins/losses.
    # rank 1 = winner. If the match was reported before, its old wins/losses are
    # taken back first, so correcting a result never double counts.
    match = get_object_or_404(Match, pk=pk)
    tournament = match.tourney
    has_bracket = TournamentBracket.objects.filter(tournament=tournament).exists()

    # in a bracket, byes and earlier rounds are locked
    if has_bracket:
        latest_round = tournament.matches.aggregate(latest=Max('round_number'))['latest']
        if match.is_bye or match.round_number < latest_round:
            return redirect('tournament_detail', pk=tournament.pk)

    if request.method == 'POST':
        participants = list(match.participants.select_related('player'))

        # read the scores typed into the form
        for part in participants:
            try:
                part.score = max(0, int(request.POST.get(f'score_{part.pk}', 0)))
            except (TypeError, ValueError):
                part.score = 0

        # every score the same means there is no winner, so don't save
        if len(participants) > 1 and len({p.score for p in participants}) == 1:
            return render(
                request,
                "tournament/error.html",
                {"message": "All scores are the same, so there is no winner. Enter different scores and confirm again."}
            )

        # take back wins/losses from an earlier report of this match
        for part in participants:
            if part.rank is not None:
                player = part.player
                if part.rank == 1:
                    player.wins = max(0, player.wins - 1)
                else:
                    player.losses = max(0, player.losses - 1)
                player.save()

        # rank = 1 + number of players who scored higher
        for part in participants:
            part.rank = 1 + sum(1 for other in participants if other.score > part.score)
            part.save()

            player = part.player
            if part.rank == 1:
                player.wins += 1
            else:
                player.losses += 1
            player.save()

        # keep the saved bracket standings in step with the new result
        if has_bracket:
            _load_manager(tournament).save_bracket_state_to_db()

    return redirect('tournament_detail', pk=tournament.pk)


def delete_tournament(request, pk):
    # POST only so a stray link click can't delete anything.
    # Cascade also removes this tournament's registrations, matches and bracket.
    if request.method == 'POST':
        tournament = get_object_or_404(Tournament, pk=pk)
        tournament.delete()

    return redirect('dashboard')


def delete_player(request, pk):
    # POST only. Removes the player and their tournament registrations.
    # MatchParticipant protects players who are in a match, so show a message instead of crashing.
    if request.method == 'POST':
        player = get_object_or_404(Player, pk=pk)

        try:
            player.delete()
        except ProtectedError:
            return render(
                request,
                "tournament/error.html",
                {"message": f"{player.username} is in a match and can't be deleted. Delete that match's tournament first."}
            )

    return redirect('players')