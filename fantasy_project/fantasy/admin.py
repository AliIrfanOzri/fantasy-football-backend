from django.contrib import admin
from .models import Team, Player, TransferListing, Transaction

# admin.site.register(User)
admin.site.register(Team)
admin.site.register(Player)
admin.site.register(TransferListing)
admin.site.register(Transaction)