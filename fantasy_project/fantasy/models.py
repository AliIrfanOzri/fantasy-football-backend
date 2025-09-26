from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone
import random
from decimal import Decimal

POSITION_CHOICES = (
    ('GK', 'Goalkeeper'),
    ('DEF', 'Defender'),
    ('MID', 'Midfielder'),
    ('ATT', 'Attacker'),
)

def default_player_value():
    return Decimal('1000000.00')  # $1,000,000

# class User(AbstractUser):
#     # add custom fields if needed
#     team_name = models.CharField(max_length=255, blank=True, null=True)
#
#     def __str__(self):
#         return self.username

class Team(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='team')
    name = models.CharField(max_length=100)
    capital = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('5000000.00'))  # $5,000,000
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    @property
    def total_value(self):
        players_value = self.players.aggregate(total=models.Sum('value'))['total'] or Decimal('0.00')
        return players_value + self.capital

class Player(models.Model):
    name = models.CharField(max_length=120)
    position = models.CharField(max_length=4, choices=POSITION_CHOICES)
    owner = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')
    value = models.DecimalField(max_digits=20, decimal_places=2, default=default_player_value)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.position}) - {self.owner}"

class TransferListing(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name='listing')
    price = models.DecimalField(max_digits=20, decimal_places=2)
    seller = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='listings')
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)  # active until bought or cancelled

    def __str__(self):
        return f"{self.player} listed for {self.price}"

class Transaction(models.Model):
    buyer = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, related_name='purchases')
    seller = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, related_name='sales')
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, related_name='transactions')
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)  # mark inactive after settlement to indicate immutable record

    def __str__(self):
        return f"Tx {self.id}: {self.player} {self.seller} -> {self.buyer} for {self.amount}"
