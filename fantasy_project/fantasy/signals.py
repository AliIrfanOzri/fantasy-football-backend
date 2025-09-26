from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Team, Player
import random
from decimal import Decimal

@receiver(post_save, sender=User)
def create_team_and_players(sender, instance, created, **kwargs):
    if created:
        team = Team.objects.create(user=instance, name=f"{instance.username}'s Team")
        # Generate initial 20 players split roughly:
        # GK: 2, DEF: 6, MID: 6, ATT: 6 (total 20)
        position_map = [('GK', 2), ('DEF', 6), ('MID', 6), ('ATT', 6)]
        for pos, count in position_map:
            for i in range(count):
                Player.objects.create(
                    name=f"{pos}-{instance.username[:6]}-{i+1}",
                    position=pos,
                    owner=team,
                    value=Decimal('1000000.00')
                )
