from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, TeamViewSet, PlayerViewSet, TransferListingViewSet, TransactionViewSet,RegisterAPIView,ProfileAPIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'teams', TeamViewSet, basename='team')
router.register(r'players', PlayerViewSet, basename='player')
router.register(r'transfers', TransferListingViewSet, basename='listings')
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    path('auth/login', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register', RegisterAPIView.as_view(), name='auth_register'),
    path('auth/profile', ProfileAPIView.as_view(), name='auth_profile'),

    path('', include(router.urls)),
]
