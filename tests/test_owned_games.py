import asyncio

from galaxy.api.types import Game, LicenseInfo
from galaxy.api.consts import LicenseType
from galaxy.api.errors import AuthenticationRequired, AccessDenied
import pytest

# only fields important for the logic
ENTITLEMENTS = [
    {
        "offerId" : "DR:119971300",
        "offerType" : "basegame"
    }
]

OFFER = {
    "offerId" : "DR:119971300",
    "i18n": {
        "displayName": "Need for Speed SHIFT"
    }
}

def test_not_authenticated(plugin, http_client):
    loop = asyncio.get_event_loop()
    http_client.is_authenticated.return_value = False
    with pytest.raises(AuthenticationRequired):
        loop.run_until_complete(plugin.get_owned_games())

def test_no_games(authenticated_plugin, backend_client, user_id):
    loop = asyncio.get_event_loop()

    backend_client.get_entitlements.return_value = []

    result = loop.run_until_complete(authenticated_plugin.get_owned_games())
    backend_client.get_entitlements.assert_called_with(user_id)
    assert result == []

def test_own_game(authenticated_plugin, backend_client, user_id):
    loop = asyncio.get_event_loop()

    backend_client.get_entitlements.return_value = ENTITLEMENTS
    backend_client.get_offer.return_value = OFFER

    result = loop.run_until_complete(authenticated_plugin.get_owned_games())
    backend_client.get_entitlements.assert_called_with(user_id)
    offer_id = OFFER["offerId"]
    backend_client.get_offer.assert_called_with(offer_id)

    assert result == [
        Game(
            "DR:119971300",
            "Need for Speed SHIFT",
            None,
            LicenseInfo(LicenseType.SinglePurchase, None)
        )
    ]

def test_access_denied(authenticated_plugin, backend_client, user_id):
    loop = asyncio.get_event_loop()

    backend_client.get_entitlements.side_effect = [AccessDenied]
    with pytest.raises(AccessDenied):
        loop.run_until_complete(authenticated_plugin.get_owned_games())
    backend_client.get_entitlements.assert_called_with(user_id)
