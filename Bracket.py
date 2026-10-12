import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .models import Tournament, TournamentRegistration, TournamentBracket

# 1. PRESETS & CUSTOM GAME CONFIGURATION

GAME_PRESETS = {
    # CARD GAMES (1v1)
    "pokemon_tcg": {"name": "Pokémon TCG", "heat_size": 2, "advance_per_heat": 1, "type": "1v1"},
    "yugioh": {"name": "Yu-Gi-Oh!", "heat_size": 2, "advance_per_heat": 1, "type": "1v1"},
    "magic_the_gathering": {"name": "Magic: The Gathering", "heat_size": 2, "advance_per_heat": 1, "type": "1v1"},

    # FIGHTING GAMES (1v1)
    "mortal_kombat": {"name": "Mortal Kombat", "heat_size": 2, "advance_per_heat": 1, "type": "1v1"},
    "street_fighter": {"name": "Street Fighter", "heat_size": 2, "advance_per_heat": 1, "type": "1v1"},
    "naruto_storm": {"name": "Naruto Ultimate Ninja Storm", "heat_size": 2, "advance_per_heat": 1, "type": "1v1"},

    # RACING GAMES (Multi-Player Heats)
    "mario_kart": {"name": "Mario Kart 8 / Deluxe", "heat_size": 4, "advance_per_heat": 2, "type": "heat"},

    # FPS / MULTIPLAYER GAMES
    "call_of_duty_ffa": {"name": "Call of Duty Free-For-All", "heat_size": 8, "advance_per_heat": 4, "type": "heat"},
}


@dataclass
class CustomGameConfig:
    game_name: str
    heat_size: int          # How many players per match/heat (e.g., 2, 3, 4, 8)
    advance_per_heat: int   # How many players move on per match (e.g., 1, 2, 4)

    def validate(self):
        if self.heat_size < 2:
            raise ValueError("Players per match must be at least 2.")
        if self.advance_per_heat >= self.heat_size:
            raise ValueError("Advancing players must be less than the total players per match.")
        if self.advance_per_heat < 1:
            raise ValueError("At least 1 player must advance per match.")


# 2. DATA MODELS

@dataclass
class Player:
    player_id: str
    username: str


@dataclass
class MatchParticipant:
    player: Player
    score: int = 0
    rank: Optional[int] = None


@dataclass
class LeaderboardEntry:
    rank: int
    player_id: str
    username: str
    wins: int
    losses: int
    points_scored: int
    stage_reached: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "player_id": self.player_id,
            "username": self.username,
            "wins": self.wins,
            "losses": self.losses,
            "points_scored": self.points_scored,
            "stage_reached": self.stage_reached
        }


class Match:
    def __init__(self, match_id: str, round_num: int, max_players: int, advance_count: int, is_bye: bool = False):
        self.match_id = match_id
        self.round_num = round_num
        self.max_players = max_players
        self.advance_count = advance_count
        self.is_bye = is_bye
        self.participants: List[MatchParticipant] = []
        self.is_completed: bool = False

    def add_player(self, player: Player):
        if len(self.participants) < self.max_players:
            self.participants.append(MatchParticipant(player=player))

    def record_scores(self, score_dict: Dict[str, int]):
        """Accepts a dictionary of {player_id: score} and assigns ranks."""
        if self.is_bye:
            return  # Byes are automatically completed

        for part in self.participants:
            if part.player.player_id in score_dict:
                part.score = score_dict[part.player.player_id]

        # Sort highest score to lowest
        self.participants.sort(key=lambda x: x.score, reverse=True)
        
        for index, part in enumerate(self.participants):
            part.rank = index + 1
            
        self.is_completed = True

    def get_advancing_players(self) -> List[Player]:
        if not self.is_completed:
            return []
        return [p.player for p in self.participants[:self.advance_count]]

    def to_dict(self) -> Dict[str, Any]:
        """JSON output for frontend rendering."""
        return {
            "match_id": self.match_id,
            "round_num": self.round_num,
            "max_players": self.max_players,
            "is_bye": self.is_bye,
            "is_completed": self.is_completed,
            "participants": [
                {
                    "player_id": p.player.player_id,
                    "username": p.player.username,
                    "score": p.score,
                    "rank": p.rank
                } for p in self.participants
            ]
        }


# 3. BRACKET GENERATOR ENGINE

class BracketPageManager:
    def __init__(
        self, 
        tournament_id: int, 
        game_key: Optional[str] = None, 
        custom_config: Optional[CustomGameConfig] = None
    ):
        self.tournament_id = tournament_id
        self.rounds: Dict[int, List[Match]] = {}

        # Look up game info from Tournament model if no explicit key is supplied
        if not game_key and not custom_config:
            try:
                tournament_obj = Tournament.objects.get(id=tournament_id)
                game_key = tournament_obj.game
            except Tournament.DoesNotExist:
                pass

        if custom_config:
            custom_config.validate()
            self.game_name = custom_config.game_name
            self.heat_size = custom_config.heat_size
            self.advance_per_heat = custom_config.advance_per_heat
            self.is_custom = True
        elif game_key and game_key in GAME_PRESETS:
            preset = GAME_PRESETS[game_key]
            self.game_name = preset["name"]
            self.heat_size = preset["heat_size"]
            self.advance_per_heat = preset["advance_per_heat"]
            self.is_custom = False
        else:
            self.game_name = "Custom Local Tournament"
            self.heat_size = 2
            self.advance_per_heat = 1
            self.is_custom = True

    def fetch_registered_players_from_system(self) -> List[Player]:
        """Pulls registered users directly from the Django database."""
        registrations = TournamentRegistration.objects.filter(
            tournament_id=self.tournament_id
        ).select_related("user")

        return [
            Player(player_id=str(reg.user.id), username=reg.user.username)
            for reg in registrations
        ]

    def generate_bracket(self) -> Dict[int, List[Match]]:
        """Pulls registered users, shuffles them, and builds Round 1 with automatic Byes."""
        registered_players = self.fetch_registered_players_from_system()

        if len(registered_players) < 2:
            raise ValueError("Cannot generate bracket: At least 2 players must be registered.")

        player_pool = registered_players.copy()
        random.shuffle(player_pool)

        self.rounds[1] = []
        match_counter = 1

        for i in range(0, len(player_pool), self.heat_size):
            group = player_pool[i:i + self.heat_size]
            is_bye = len(group) < self.heat_size

            match = Match(
                match_id=f"R1-M{match_counter}",
                round_num=1,
                max_players=self.heat_size,
                advance_count=self.advance_per_heat,
                is_bye=is_bye
            )

            for p in group:
                match.add_player(p)

            # AUTOMATIC BYE RESOLUTION
            if is_bye:
                match.is_completed = True
                for part in match.participants:
                    part.rank = 1  # Auto-advance

            self.rounds[1].append(match)
            match_counter += 1

        self.save_bracket_state_to_db()
        return self.rounds

    def advance_to_next_round(self, current_round_num: int) -> Optional[List[Match]]:
        """Advances winners and handles both Full-Lobby and 1v1 Grand Finals."""
        current_matches = self.rounds.get(current_round_num, [])

        if not all(m.is_completed for m in current_matches):
            return None

        # CHECK IF TOURNAMENT JUST FINISHED
        if len(current_matches) == 1:
            self.save_bracket_state_to_db()
            return None

        # Gather advancing players
        advancing_players: List[Player] = []
        for match in current_matches:
            advancing_players.extend(match.get_advancing_players())

        total_advancers = len(advancing_players)

        next_heat_size = self.heat_size
        next_advance_count = self.advance_per_heat

        # DYNAMIC FINALS ADAPTATION
        if total_advancers == 2:
            next_heat_size = 2
            next_advance_count = 1
        elif total_advancers <= self.heat_size and self.heat_size > 2:
            next_heat_size = total_advancers
            next_advance_count = 1

        # Build Next Round
        next_round_num = current_round_num + 1
        self.rounds[next_round_num] = []
        match_counter = 1

        for i in range(0, total_advancers, next_heat_size):
            group = advancing_players[i:i + next_heat_size]
            is_bye = len(group) < next_heat_size and len(advancing_players) > next_heat_size

            match = Match(
                match_id=f"R{next_round_num}-M{match_counter}",
                round_num=next_round_num,
                max_players=next_heat_size,
                advance_count=next_advance_count,
                is_bye=is_bye
            )
            for p in group:
                match.add_player(p)

            if is_bye:
                match.is_completed = True
                for part in match.participants:
                    part.rank = 1

            self.rounds[next_round_num].append(match)
            match_counter += 1

        self.save_bracket_state_to_db()
        return self.rounds[next_round_num]

    def calculate_leaderboard(self) -> List[LeaderboardEntry]:
        """Scans all rounds/matches and constructs overall tournament standings."""
        stats: Dict[str, Dict[str, Any]] = {}

        # 1. Initialize stats for all registered players
        all_players = self.fetch_registered_players_from_system()
        for p in all_players:
            stats[p.player_id] = {
                "username": p.username,
                "wins": 0,
                "losses": 0,
                "points_scored": 0,
                "highest_round": 1,
                "highest_rank": 999
            }

        # 2. Iterate across all completed matches
        total_rounds = max(self.rounds.keys()) if self.rounds else 1

        for round_num, matches in self.rounds.items():
            for m in matches:
                if not m.is_completed:
                    continue

                advancing_ids = {p.player_id for p in m.get_advancing_players()}

                for part in m.participants:
                    p_id = part.player.player_id
                    if p_id not in stats:
                        stats[p_id] = {
                            "username": part.player.username,
                            "wins": 0,
                            "losses": 0,
                            "points_scored": 0,
                            "highest_round": 1,
                            "highest_rank": 999
                        }

                    stats[p_id]["points_scored"] += part.score
                    stats[p_id]["highest_round"] = max(stats[p_id]["highest_round"], round_num)

                    if part.rank is not None:
                        stats[p_id]["highest_rank"] = min(stats[p_id]["highest_rank"], part.rank)

                    # Mark win/loss based on advancement cutoff (ignore Byes for stats)
                    if not m.is_bye:
                        if p_id in advancing_ids:
                            stats[p_id]["wins"] += 1
                        else:
                            stats[p_id]["losses"] += 1

        # 3. Sort players (Highest Round -> Best Match Rank -> Total Points -> Wins)
        sorted_players = sorted(
            stats.items(),
            key=lambda x: (
                x[1]["highest_round"],
                -x[1]["highest_rank"],
                x[1]["points_scored"],
                x[1]["wins"]
            ),
            reverse=True
        )

        # 4. Format into LeaderboardEntry list
        leaderboard: List[LeaderboardEntry] = []
        for rank, (p_id, data) in enumerate(sorted_players, start=1):
            if data["highest_round"] == total_rounds and data["highest_rank"] == 1:
                stage = "Champion 🏆"
            elif data["highest_round"] == total_rounds:
                stage = "Finalist"
            else:
                stage = f"Round {data['highest_round']}"

            leaderboard.append(
                LeaderboardEntry(
                    rank=rank,
                    player_id=p_id,
                    username=data["username"],
                    wins=data["wins"],
                    losses=data["losses"],
                    points_scored=data["points_scored"],
                    stage_reached=stage
                )
            )

        return leaderboard

    def save_bracket_state_to_db(self):
        """Persists the serialized bracket state + leaderboard into Django database JSONField."""
        state_data = self.get_bracket_json()
        current_round = max(self.rounds.keys()) if self.rounds else 1
        
        TournamentBracket.objects.update_or_create(
            tournament_id=self.tournament_id,
            defaults={
                "current_round": current_round,
                "bracket_data": state_data
            }
        )

    def get_bracket_json(self) -> Dict[str, Any]:
        """Return full bracket + leaderboard JSON payload for frontend views."""
        return {
            "tournament_id": self.tournament_id,
            "game_name": self.game_name,
            "is_custom": self.is_custom,
            "rounds": {
                round_num: [m.to_dict() for m in matches]
                for round_num, matches in self.rounds.items()
            },
            "leaderboard": [entry.to_dict() for entry in self.calculate_leaderboard()]
        }
        
