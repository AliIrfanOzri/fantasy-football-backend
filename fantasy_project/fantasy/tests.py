from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
# from .models import User, Team, Player, TransferListing
from decimal import Decimal

# class TransferTests(TestCase):
#     def setUp(self):
#         self.client = APIClient()
#         self.user1 = User.objects.create_user(username='u1', password='pass1')
#         self.user2 = User.objects.create_user(username='u2', password='pass2')
#         # teams and players created by signal
#
#     def authenticate(self, user):
#         resp = self.client.post('/api/token/', {'username': user.username, 'password': 'pass1' if user.username=='u1' else 'pass2'})
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
#
#     def test_listing_and_buy(self):
#         # user1 lists a player
#         self.authenticate(self.user1)
#         team1 = self.user1.team
#         player = team1.players.first()
#         resp = self.client.post('/listings/', {'player_id': player.id, 'price': '1000000.00'})
#         self.assertEqual(resp.status_code, 201)
#         listing_id = resp.data['id']
#
#         # user2 buys
#         self.authenticate(self.user2)
#         resp = self.client.post(f'/listings/{listing_id}/buy/')
#         self.assertEqual(resp.status_code, 201)
#         # ensure ownership changed
#         player.refresh_from_db()
#         self.assertEqual(player.owner, self.user2.team)


from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from fantasy.models import Team, Player, TransferListing, Transaction

class FantasyFootballAPITest(APITestCase):

    def setUp(self):
        # Create test user
        # self.user = User.objects.create_user(username="user1", password="Password123!")
        # self.user2 = User.objects.create_user(username="user2", password="Password123!")
        #
        # # Login user1 and store JWT
        # response = self.client.post("/api/auth/login/", {
        #     "username": "user1",
        #     "password": "Password123!"
        # })
        # self.token = response.data["access"]
        # self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

        self.client = APIClient()
        # Create test user
        self.user = User.objects.create_user(username="test", password="pass")
        response = self.client.post("/api/token/", {"username": "test", "password": "pass"}, format="json")
        assert response.status_code == 200, response.content
        self.token = response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    # ---------------------------
    # 🔹 AUTH TESTS
    # ---------------------------
    def test_user_registration(self):
        response = self.client.post("/api/user", {
            "username": "newuser",
            "password": "Password123!",
            "email": "new@user.com"
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_user_login(self):
        response = self.client.post("/api/user", {
            "username": "user1",
            "password": "Password123!"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    # def test_user_profile(self):
    #     response = self.client.get("/api/auth/profile/")
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(response.data["username"], "user1")

    # ---------------------------
    # 🔹 TEAM TESTS
    # ---------------------------
    def test_get_my_team(self):
        response = self.client.get("/api/teams/my/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("players", response.data)

    def test_team_capital_is_not_directly_modifiable(self):
        team = Team.objects.get(user=self.user)
        response = self.client.patch(f"/api/teams/{team.id}/", {"capital": 9999999})
        self.assertNotEqual(team.capital, 9999999)  # ensure not updated
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------------------------
    # 🔹 PLAYER TESTS
    # ---------------------------
    def test_list_players(self):
        response = self.client.get("/api/players/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_players_by_position(self):
        response = self.client.get("/api/players/?position=goalkeeper")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ---------------------------
    # 🔹 TRANSFER MARKET TESTS
    # ---------------------------
    def test_list_a_player_for_sale(self):
        player = Player.objects.filter(team__user=self.user).first()
        response = self.client.post("/api/transfers/", {
            "player": player.id,
            "price": 2000000
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_list_player_not_owned(self):
        player = Player.objects.filter(team__user=self.user2).first()
        response = self.client.post("/api/transfers/", {
            "player": player.id,
            "price": 2000000
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_buy_player_success(self):
        # user2 lists player for sale
        self.client.credentials()  # reset
        resp_login = self.client.post("/api/auth/login/", {
            "username": "user2", "password": "Password123!"
        })
        token2 = resp_login.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token2}")

        player = Player.objects.filter(team__user=self.user2).first()
        transfer = TransferListing.objects.create(player=player, price=1000000, seller=self.user2.team)

        # user1 buys it
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(f"/api/transfers/{transfer.id}/buy/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_buy_player_insufficient_capital(self):
        player = Player.objects.filter(team__user=self.user2).first()
        transfer = TransferListing.objects.create(player=player, price=100000000, seller=self.user2.team)
        response = self.client.post(f"/api/transfers/{transfer.id}/buy/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------------------------
    # 🔹 TRANSACTION HISTORY
    # ---------------------------
    def test_transaction_history(self):
        response = self.client.get("/api/transactions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

