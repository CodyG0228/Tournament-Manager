from django.contrib import admin
from .models import Tournament, Player, TournamentRegistration, Match, MatchParticipant, TournamentBracket


#all tables are manageable in /admin/.
admin.site.register(Tournament)
admin.site.register(Player)
admin.site.register(TournamentRegistration)
admin.site.register(Match)
admin.site.register(MatchParticipant)
admin.site.register(TournamentBracket)
