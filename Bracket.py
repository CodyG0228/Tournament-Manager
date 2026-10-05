import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

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
    #!!!!!
    #Pass custom rules entered by an admin on the frontend page into this class.
    #!!!!!
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
        # Return all players in match up to the advance_count cutoff
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
        tournament_id: str, 
        game_key: Optional[str] = None, 
        custom_config: Optional[CustomGameConfig] = None
    ):
        self.tournament_id = tournament_id
        self.rounds: Dict[int, List[Match]] = {}

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
        #!!!!!
        #Connect this function to your registration DB table.
        #!!!!!
        # Simulated registration pool (17 players to demonstrate the odd count & bye handling)
        mock_registrations = [
            {"id": f"usr_{i:02d}", "name": f"Player_{i}"} for i in range(1, 18)
        ]
        return [Player(player_id=p["id"], username=p["name"]) for p in mock_registrations]

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

            # Detect if this group has fewer players than heat_size (e.g. 17th player)
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
                print(f"ℹ️ {group[0].username} received a Round 1 BYE (Auto-advancing to Round 2).")

            self.rounds[1].append(match)
            match_counter += 1

        self.save_bracket_state_to_db()
        return self.rounds

    def advance_to_next_round(self, current_round_num: int) -> Optional[List[Match]]:
        """Advances winners and handles both Full-Lobby and 1v1 Grand Finals."""
        current_matches = self.rounds.get(current_round_num, [])

        if not all(m.is_completed for m in current_matches):
            print(f"Cannot advance: Round {current_round_num} has incomplete matches.")
            return None

        # CHECK IF TOURNAMENT JUST FINISHED
        if len(current_matches) == 1:
            winning_match = current_matches[0]
            champion = winning_match.participants[0].player.username
            print(f"\n🏆 TOURNAMENT COMPLETED! 🏆")
            print(f"Grand Champion: {champion}")
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
            print("\n⚡ Final 2 players reached! Adjusting Grand Finals to a 1v1 match.")
            next_heat_size = 2
            next_advance_count = 1
        elif total_advancers <= self.heat_size and self.heat_size > 2:
            print(f"\n🏁 Final {total_advancers} players reached! Setting up Grand Finals heat.")
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
                print(f"ℹ️ {group[0].username} received a Round {next_round_num} BYE.")

            self.rounds[next_round_num].append(match)
            match_counter += 1

        self.save_bracket_state_to_db()
        return self.rounds[next_round_num]

    def save_bracket_state_to_db(self):
        #!!!!!
        #Write the bracket JSON to your database here.
        #!!!!!
        pass

    def get_bracket_json(self) -> Dict[str, Any]:
        #!!!!!
        #Return this JSON payload to your frontend view.
        #!!!!!

        return {
            "tournament_id": self.tournament_id,
            "game_name": self.game_name,
            "is_custom": self.is_custom,
            "rounds": {
                round_num: [m.to_dict() for m in matches]
                for round_num, matches in self.rounds.items()
            }
        }



# 4. DEMONSTRATION RUN (17-PLAYER 1v1 CARD / FIGHTING GAME TOURNAMENT)

if __name__ == "__main__":
    print("=== DEMO: 17 PLAYERS IN A 1v1 TOURNAMENT WITH AUTOMATIC BYE ===")
    
    # Initialize 17-player 1v1 tournament (Yu-Gi-Oh! / Pokémon TCG / Fighting Game)
    tourney = BracketPageManager(tournament_id="card_17_demo", game_key="yugioh")
    tourney.generate_bracket()

    print(f"\n--- ROUND 1 ({len(tourney.rounds[1])} Matches Generated) ---")
    for m in tourney.rounds[1]:
        players = [p.player.username for p in m.participants]
        if m.is_bye:
            print(f"{m.match_id}: {players[0]} [AUTO-ADVANCED BYE]")
        else:
            print(f"{m.match_id}: {players[0]} vs {players[1]}")

    # Record scores for the 8 playable matches (R1-M1 through R1-M8)
    for i in range(8):
        m = tourney.rounds[1][i]
        p1_id = m.participants[0].player.player_id
        p2_id = m.participants[1].player.player_id
        m.record_scores({p1_id: 2, p2_id: 1})  # Player 1 wins each match

    # Advance to Round 2 (8 winners from played matches + 1 Bye recipient = 9 players)
    tourney.advance_to_next_round(1)

    print(f"\n--- ROUND 2 ({len(tourney.rounds[2])} Matches Generated with 9 Advancers) ---")
    for m in tourney.rounds[2]:
        players = [p.player.username for p in m.participants]
        if m.is_bye:
            print(f"{m.match_id}: {players[0]} [AUTO-ADVANCED BYE]")
        else:
            print(f"{m.match_id}: {players[0]} vs {players[1]}")