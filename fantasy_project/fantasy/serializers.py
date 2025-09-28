from rest_framework import serializers
from .models import Team, Player, TransferListing, Transaction
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from decimal import Decimal
import random

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = ('id','username','email','password','first_name','last_name')

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name']


    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class PlayerSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = Player
        fields = ('id','name','position','owner','value','created_at')
        read_only_fields = ('value','owner','created_at')  # value cannot be changed via API

class TeamSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    players = PlayerSerializer(many=True, read_only=True)
    total_value = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    class Meta:
        model = Team
        fields = ('id','name','user','capital','players','created_at','total_value')
        read_only_fields = ('capital',)  # cannot modify via API

class TeamCreateSerializer(serializers.ModelSerializer):
    players = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )

    class Meta:
        model = Team
        fields = ('id','name','user','capital','players','created_at','total_value')
        read_only_fields = ('capital',)  # cannot modify via API

    def validate(self, data):
        player_ids = data.get("players", [])
        players = Player.objects.filter(id__in=player_ids, owner__isnull=True)

        # Ensure all players are available
        if players.count() != len(player_ids):
            raise serializers.ValidationError("Some players are not available or already owned.")

        # ✅ 20 player validation
        if len(player_ids) > 20:
            raise serializers.ValidationError("A team must have exactly 20 players.")

        # ✅ Position validation
        required_positions = {
            "GK": 2,
            "DEF": 6,
            "MID": 6,
            "ATT": 6,
        }

        position_counts = {pos: 0 for pos in required_positions}
        for p in players:
            if p.position in position_counts:
                position_counts[p.position] += 1

        for pos, required_count in required_positions.items():
            if position_counts[pos] > required_count:
                raise serializers.ValidationError(
                    f"Invalid team composition: {pos} must have {required_count}, "
                    f"but you selected {position_counts[pos]}."
                )

        # ✅ Budget validation
        total_cost = sum(p.value for p in players)
        if total_cost > 5000000:  # initial budget
            raise serializers.ValidationError("Selected players exceed initial budget of $5,000,000.")

        return data

    def create(self, validated_data):
        player_ids = validated_data.pop("players")
        user = self.context["request"].user

        if hasattr(user, "team"):
            raise serializers.ValidationError("You already have a team.")

        team = Team.objects.create(user=user,name=validated_data["name"], capital=5000000)

        players = Player.objects.filter(id__in=player_ids, owner__isnull=True)
        total_cost = sum(p.value for p in players)

        # Deduct from capital
        team.capital -= total_cost
        team.save()

        # Assign players to this team
        players.update(owner=team)

        return team

class TransferListingSerializer(serializers.ModelSerializer):
    seller = serializers.StringRelatedField(read_only=True)
    player = PlayerSerializer(read_only=True)
    player_id = serializers.PrimaryKeyRelatedField(queryset=Player.objects.all(), write_only=True, source='player')
    class Meta:
        model = TransferListing
        fields = ('id','player','player_id','price','seller','created_at','active')

    def validate(self, attrs):
        player = attrs['player']
        request = self.context['request']
        if player.owner.user != request.user:
            raise serializers.ValidationError("Only the owner can list this player.")
        # Ensure player isn't already listed
        if hasattr(player, 'listing') and player.listing.active:
            raise serializers.ValidationError("This player is already listed.")
        return attrs

    def create(self, validated_data):
        player = validated_data['player']
        seller = player.owner
        price = validated_data['price']
        print("create",player,seller,price)
        listing = TransferListing.objects.create(player=player, seller=seller, price=price, active=True)
        return listing

class TransactionSerializer(serializers.ModelSerializer):
    buyer = serializers.StringRelatedField(read_only=True)
    seller = serializers.StringRelatedField(read_only=True)
    player = PlayerSerializer(read_only=True)
    class Meta:
        model = Transaction
        fields = ('id','buyer','seller','player','amount','created_at','active')
        read_only_fields = fields  # transactions are read-only via API
