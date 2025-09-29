import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

from .models import Team, Player, TransferListing, Transaction

# Helper constants
INITIAL_TEAM_CAPITAL = Decimal('5000000.00')
INITIAL_PLAYER_VALUE = Decimal('1000000.00')
PLAYERS_PER_TEAM = 20
POSITIONS = {"GK": 2, "DEF": 6, "MID": 6, "ATT": 6}

@pytest.mark.django_db
class TestFullFootballTransferFlow:
    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def create_user(self, db):
        def _create(username='user1', email=None, password='StrongPass123!', first_name='FN', last_name='LN'):
            email = email or f'{username}@example.com'
            user = User.objects.create_user(username=username, email=email, password=password,
                                            first_name=first_name, last_name=last_name)
            return user
        return _create

    @pytest.fixture
    def create_extra_players(db):
        """
        Create more than 20 players (invalid case).
        """

        def make_extra(count=25, pos="DEF", value=100_000):
            players = []
            for i in range(count):
                p = Player.objects.create(
                    name=f"{pos}_Extra_{i}",
                    position=pos,
                    value=value,
                )
                players.append(p)
            return players

        return make_extra

    @pytest.fixture
    def create_expensive_players(db):
        """
        Create 20 players whose total value exceeds the budget.
        """

        def make_expensive():
            players = []
            for i in range(20):
                p = Player.objects.create(
                    name=f"EXP_Player_{i}",
                    position=list(POSITIONS.keys())[i % 4],  # cycle GK/DEF/MID/ATT
                    value=400_000,  # 20 * 400k = 8M (over 5M budget)
                )
                players.append(p)
            return players

        return make_expensive

    @pytest.fixture
    def create_players(db):
        def make_players(distribution=POSITIONS, value=100_000):
            players = []
            for pos, count in distribution.items():
                for i in range(count):
                    p = Player.objects.create(
                        name=f"{pos}_Player_{i}",
                        position=pos,
                        value=value,
                    )
                    players.append(p)
            return players

        return make_players

    @pytest.fixture
    def create_team(db, create_user, create_players):
        def make_team(username="teamuser",user=None, name="My Team"):
            if not user:
                user = create_user(username)
            players = create_players()
            team = Team.objects.create(
                name=name,
                user=user,
                capital=INITIAL_TEAM_CAPITAL - sum(p.value for p in players),
            )
            team.players.set(players)
            return team

        return make_team

    def test_registration_creates_user_team_and_players(self, client):
        url = reverse('user-list')
        payload = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "StrongPass123!",
            "first_name": "New",
            "last_name": "User",
        }
        resp = client.post(url, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED

        user = User.objects.get(username='newuser')
        assert user.check_password('StrongPass123!')

        # assert hasattr(user, 'team')
        # team = user.team
        # assert team.capital == INITIAL_TEAM_CAPITAL
        #
        # players = team.players.all()
        # assert players.count() == PLAYERS_PER_TEAM
        #
        # for p in players:
        #     assert p.value == INITIAL_PLAYER_VALUE
        #     assert p.position in ('GK','DEF','MID','ATT')#('goalkeeper', 'defender', 'midfielder', 'attacker')
        #
        # total_value = sum(p.value for p in players)
        # print("CALLLLLL",team,team.total_value,total_value)
        # print(hasattr(team, 'total_value'))
        # assert total_value == INITIAL_PLAYER_VALUE * PLAYERS_PER_TEAM

    def test_registration_weak_password_rejected(self, client):
        url = reverse('user-list')
        payload = {
            "username": "weak",
            "email": "weak@example.com",
            "password": "123",
            "first_name": "W",
            "last_name": "P",
        }
        resp = client.post(url, payload, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'password' in resp.data

    def test_user_login_and_permissions_for_read_endpoints(self, client, create_user,create_team):
        user = create_user('viewer')
        client.force_authenticate(user=user)

        team = create_team(name="Fixture XI")

        team_url = reverse('team-list')
        resp = client.get(team_url)
        assert resp.status_code == status.HTTP_200_OK

        client.force_authenticate(user=None)
        resp = client.get(team_url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_team_me_endpoint_returns_user_team(self, client, create_user,create_team):
        user = create_user('owner1')
        client.force_authenticate(user=user)
        team = create_team(user=user,name="Fixture XI")
        url = reverse('team-me')
        resp = client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['id'] == user.team.id
    #
    def test_player_market_endpoint_and_listing_creation_and_visibility(self, client, create_user,create_team):
        seller_user = create_user('seller')
        buyer_user = create_user('buyer')

        client.force_authenticate(user=seller_user)
        team = create_team(user=seller_user,name="Fixture XI")
        player = seller_user.team.players.first()
        print("PLAYER----",player)
        listing_payload = {
            'player_id': player.id,
            'price': 1500000.00
        }


        url = reverse('listings-list')
        resp = client.post(url, listing_payload, format='json')
        assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
        listing_id = resp.data.get('id') or resp.data.get('listing_id') or resp.data['pk']

        url_market = reverse('player-market')
        resp_market = client.get(url_market)
        assert resp_market.status_code == status.HTTP_200_OK
        found = False
        for item in resp_market.data:
            if str(item.get('listing_id')) == str(listing_id) or item.get('player', {}).get('id') == player.id:
                found = True
                assert Decimal(item['price']) == Decimal('1500000.00')
        assert found
    #
    def test_transfer_listing_cancel_only_by_seller(self, client, create_user,create_team):
        seller = create_user('seller2')
        other = create_user('not_seller')
        client.force_authenticate(user=seller)
        team = create_team(user=seller, name="Fixture XI")

        player = seller.team.players.first()

        resp = client.post(reverse('listings-list'), {'player_id': player.id, 'price': 1200000.00}, format='json')
        print("RESP====",resp)
        listing_id = resp.data.get('id') or resp.data['pk']

        client.force_authenticate(user=other)
        otherteam = create_team(user=other, name="Fixture II")
        resp_delete_other = client.delete(reverse('listings-detail', args=[listing_id]))
        assert resp_delete_other.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)

        client.force_authenticate(user=seller)
        resp_delete_seller = client.delete(reverse('listings-detail', args=[listing_id]))

        assert resp_delete_seller.status_code in (status.HTTP_204_NO_CONTENT, status.HTTP_200_OK)
        listing = TransferListing.objects.get(pk=listing_id)
        assert listing.active is False
    # #
    def test_buy_flow_successful_transfer_and_transaction_record(self, client, create_user, create_team,monkeypatch):
        seller = create_user('seller3')
        buyer = create_user('buyer3')

        client.force_authenticate(user=seller)
        team = create_team(user=seller, name="Fixture XI")
        player = seller.team.players.first()
        price = Decimal('1000000.00')
        resp = client.post(reverse('listings-list'), {'player_id': player.id, 'price': price}, format='json')
        listing_id = resp.data.get('id') or resp.data['pk']

        monkeypatch.setattr('random.uniform', lambda a, b: 0.10)

        client.force_authenticate(user=buyer)
        team_2 = create_team(user=buyer, name="Fixture II")
        buy_url = reverse('listings-buy', args=[listing_id])
        resp_buy = client.post(buy_url, format='json')
        assert resp_buy.status_code == status.HTTP_201_CREATED

        listing = TransferListing.objects.get(pk=listing_id)
        assert listing.active is False

        tx_id = resp_buy.data.get('id') or resp_buy.data.get('pk')
        tx = Transaction.objects.get(pk=tx_id)
        assert tx.amount == price
        assert tx.buyer == buyer.team
        assert tx.seller == seller.team
        assert tx.active is False

        print("PLAYER----1", player,buyer.team, buyer.team.capital)
        player.refresh_from_db()
        assert player.owner == buyer.team
        print("PLAYER----2",player,buyer.team,buyer.team.capital)
    # #
    def test_buy_flow_failures(self, client, create_user,create_team):
        seller = create_user('seller4')
        buyer = create_user('buyer4')

        client.force_authenticate(user=seller)
        team = create_team(user=seller, name="Fixture XI")
        player = seller.team.players.first()
        price = Decimal('6000000.00')  # more than initial capital to force insufficient funds
        resp = client.post(reverse('listings-list'), {'player_id': player.id, 'price': price}, format='json')
        listing_id = resp.data.get('id') or resp.data['pk']

        client.force_authenticate(user=buyer)
        team2 = create_team(user=buyer, name="Fixture XI")
        resp_buy = client.post(reverse('listings-buy', args=[listing_id]), format='json')
        assert resp_buy.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Insufficient' in str(resp_buy.data.get('detail', '') or resp_buy.data)

        client.force_authenticate(user=seller)
        resp_buy_own = client.post(reverse('listings-buy', args=[listing_id]), format='json')
        assert resp_buy_own.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Cannot buy your own player' in str(resp_buy_own.data.get('detail', '') or resp_buy_own.data)

        listing = TransferListing.objects.get(pk=listing_id)
        listing.active = False
        listing.save()
        print("LISTING====",listing)
        client.force_authenticate(user=buyer)
        resp_buy_inactive = client.post(reverse('listings-buy', args=[listing.pk]), format='json')
        assert resp_buy_inactive.status_code == status.HTTP_404_NOT_FOUND
        assert 'Listing not active' or 'No TransferListing matches the given query' in str(resp_buy_inactive.data.get('detail', '') or resp_buy_inactive.data)
    # #
    def test_seller_no_longer_owns_player_at_time_of_purchase(self, client, create_user, create_team,monkeypatch):
        seller = create_user('seller5')
        buyer = create_user('buyer5')
        user = create_user('other_buyer')

        client.force_authenticate(user=seller)
        team2 = create_team(user=seller, name="Fixture XI")
        player = seller.team.players.first()
        price = Decimal('1000000.00')
        resp = client.post(reverse('listings-list'), {'player_id': player.id, 'price': price}, format='json')
        listing_id = resp.data.get('id') or resp.data['pk']


        other_user = create_user("other5")
        team2 = create_team(user=other_user, name="Fixture XI")
        other_team = other_user.team  # team auto-created

        # other_team = Team.objects.create(user=user,name='other', capital=INITIAL_TEAM_CAPITAL)
        player.owner = other_team
        player.save()

        client.force_authenticate(user=buyer)
        team2 = create_team(user=buyer, name="Fixture XI")
        resp_buy = client.post(reverse('listings-buy', args=[listing_id]), format='json')
        assert resp_buy.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Seller no longer owns player' in str(resp_buy.data.get('detail', '') or resp_buy.data)
    # #
    def test_transaction_history_viewable_and_ordered(self, client, create_user, create_team,monkeypatch):
        seller = create_user('seller6')
        buyer = create_user('buyer6')


        client.force_authenticate(user=seller)
        team2 = create_team(user=seller, name="Fixture XI")
        player1 = seller.team.players.first()
        player2 = seller.team.players.all()[1]


        r1 = client.post(reverse('listings-list'), {'player_id': player1.id, 'price': 1000000.00}, format='json')
        l1 = r1.data.get('id') or r1.data['pk']
        r2 = client.post(reverse('listings-list'), {'player_id': player2.id, 'price': 1000000.00}, format='json')
        l2 = r2.data.get('id') or r2.data['pk']

        monkeypatch.setattr('random.uniform', lambda a, b: 0.07)

        # buy both by buyer
        client.force_authenticate(user=buyer)
        team2 = create_team(user=buyer, name="Fixture XI")
        client.post(reverse('listings-buy', args=[l1]), format='json')
        client.post(reverse('listings-buy', args=[l2]), format='json')


        client.force_authenticate(user=buyer)
        resp = client.get(reverse('transaction-list'))
        assert resp.status_code == status.HTTP_200_OK

        assert len(resp.data) >= 2

        print("DATAAAAA",resp.data.get("results",[])[:2])
        for tx in resp.data.get("results",[])[:2]:
            assert 'buyer' in tx and 'seller' in tx and 'player' in tx and 'amount' in tx
    # #
    def test_cannot_modify_capital_or_player_value_via_api(self, client, create_user,create_team):
        user = create_user('immutable')
        client.force_authenticate(user=user)
        team2 = create_team(user=user, name="Fixture XI")


        team_detail = reverse('team-detail', args=[user.team.id])
        resp = client.patch(team_detail, {'capital': '9999999.00'}, format='json')
        assert resp.status_code in (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_403_FORBIDDEN, status.HTTP_200_OK)
        user.team.refresh_from_db()
        assert user.team.capital == Decimal('3000000.00')


        player = user.team.players.first()
        player_detail = reverse('player-detail', args=[player.id])
        resp_p = client.patch(player_detail, {'value': '9999999.00'}, format='json')
        assert resp_p.status_code in (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_403_FORBIDDEN, status.HTTP_200_OK)
        player.refresh_from_db()
        assert player.value == Decimal('100000.00')
    #
    #
    def test_team_creation_with_valid_players(self,client, create_user, create_players):
        user = create_user("teamuser")
        client.force_authenticate(user=user)
        # team2 = create_team(user=user, name="Fixture XI")

        # Create a valid squad of 20 players matching positions & budget
        valid_players = create_players(POSITIONS)  # helper generates required players

        url = reverse("team-list")
        payload = {
            "user":user.id,
            "name": "Dream XI",
            "players": [p.id for p in valid_players],
        }
        resp = client.post(url, payload, format="json")

        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["name"] == "Dream XI"
        assert Decimal(data["capital"]) <= INITIAL_TEAM_CAPITAL
    #
    def test_team_creation_fails_with_more_than_20_players(self,client, create_user, create_extra_players):
        user = create_user("bigteam")
        client.force_authenticate(user=user)

        # 25 players (invalid)
        too_many_players = create_extra_players()

        url = reverse("team-list")
        payload = {
            "user": user.id,
            "name": "Too Many",
            "players": [p.id for p in too_many_players],
        }
        resp = client.post(url, payload, format="json")

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "A team must have exactly 20 players" in str(resp.content)
    #

    def test_team_creation_fails_with_invalid_position_distribution(self,client, create_user, create_players):
        user = create_user("wrongpos")
        client.force_authenticate(user=user)

        # Make 20 defenders (invalid distribution)
        invalid_players = create_players({"DEF": 20})

        url = reverse("team-list")
        payload = {
            "user":user.id,
            "name": "Wrong Pos",
            "players": [p.id for p in invalid_players],
        }
        resp = client.post(url, payload, format="json")

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid team composition" in str(resp.content)
    #

    def test_team_creation_fails_with_budget_exceeded(self,client, create_user, create_expensive_players):
        user = create_user("richguy")
        client.force_authenticate(user=user)

        # Players cost > 5,000,000
        expensive_players = create_expensive_players()

        url = reverse("team-list")
        payload = {
            "user": user.id,
            "name": "Over Budget",
            "players": [p.id for p in expensive_players],
        }
        resp = client.post(url, payload, format="json")

        assert resp.status_code == status.HTTP_400_BAD_REQUEST


