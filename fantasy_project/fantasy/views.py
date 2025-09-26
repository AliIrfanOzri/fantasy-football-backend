from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from decimal import Decimal
import random
from django.contrib.auth.models import User
from .models import Team, Player, TransferListing, Transaction
from .serializers import (UserRegisterSerializer, TeamSerializer,
                          PlayerSerializer, TransferListingSerializer,
                          TransactionSerializer)

from rest_framework.permissions import IsAuthenticated, AllowAny

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer

    def get_permissions(self):
        if self.action in ['create']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        return serializer.save()  # signals create team/players


class TeamViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Team.objects.prefetch_related('players').all()
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # users can list all teams, or to get own team
        return Team.objects.prefetch_related('players').all()

    @action(detail=False, methods=['get'])
    def me(self, request):
        team = request.user.team
        serializer = self.get_serializer(team)
        return Response(serializer.data)


class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Player.objects.select_related('owner').all()
    serializer_class = PlayerSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def market(self, request):
        # players on sale (active)
        listings = TransferListing.objects.filter(active=True)
        data = []
        for l in listings:
            data.append({
                'listing_id': l.id,
                'player': PlayerSerializer(l.player, context={'request': request}).data,
                'price': l.price,
                'seller': l.seller.name,
            })
        return Response(data)


class TransferListingViewSet(viewsets.ModelViewSet):
    queryset = TransferListing.objects.select_related('player','seller').all()
    serializer_class = TransferListingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TransferListing.objects.filter(active=True)

    def perform_destroy(self, instance):
        # cancel (mark inactive) only by seller
        user_team = self.request.user.team
        if instance.seller != user_team:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only seller can cancel this listing.")
        instance.active = False
        instance.save()

    @action(detail=True, methods=['post'])
    def buy(self, request, pk=None):
        """
        Purchase a player listed for sale.
        """
        listing = self.get_object()
        buyer_team = request.user.team
        seller_team = listing.seller

        if not listing.active:
            return Response({'detail':'Listing not active.'}, status=status.HTTP_400_BAD_REQUEST)
        if buyer_team == seller_team:
            return Response({'detail':'Cannot buy your own player.'}, status=status.HTTP_400_BAD_REQUEST)

        price = listing.price
        if buyer_team.capital < price:
            return Response({'detail':'Insufficient capital.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # debit buyer
            buyer = Team.objects.select_for_update().get(pk=buyer_team.pk)
            seller = Team.objects.select_for_update().get(pk=seller_team.pk)
            player = Player.objects.select_for_update().get(pk=listing.player.pk)

            # Verify ownership still holds
            if player.owner != seller:
                return Response({'detail':'Seller no longer owns player.'}, status=status.HTTP_400_BAD_REQUEST)

            # Transfer money
            buyer.capital = buyer.capital - price
            seller.capital = seller.capital + price

            buyer.save()
            seller.save()

            # Change player owner
            player.owner = buyer
            # Random value increase: e.g., between 5% and 15%
            increase_pct = Decimal(random.uniform(0.05, 0.15))
            new_value = (player.value * (Decimal('1.0') + increase_pct)).quantize(Decimal('0.01'))
            player.value = new_value
            player.save()

            # record transaction (initially active True, then we mark inactive per your constraints)
            tx = Transaction.objects.create(
                buyer=buyer,
                seller=seller,
                player=player,
                amount=price,
                active=True,
            )

            # Mark listing inactive (can't be reused)
            listing.active = False
            listing.save()

            # As per constraint: "Once a transfer is completed, the corresponding transfer entry should be marked as inactive and cannot be deleted."
            # Transaction record should be marked inactive (so it's immutable?) — interpretation: mark tx.active=False to indicate completed and immutable.
            tx.active = False
            tx.save()

            serializer = TransactionSerializer(tx, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.select_related('buyer','seller','player').all().order_by('-created_at')
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # allow all users to view transaction history (global). Could limit to user's transactions via query param.
        return self.queryset
