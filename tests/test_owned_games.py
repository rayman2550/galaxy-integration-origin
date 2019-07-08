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

@pytest.mark.asyncio
async def test_not_authenticated(plugin, http_client):
    http_client.is_authenticated.return_value = False
    with pytest.raises(AuthenticationRequired):
        await plugin.get_owned_games()

@pytest.mark.asyncio
async def test_no_games(authenticated_plugin, backend_client, user_id):
    backend_client.get_entitlements.return_value = []

    result = await authenticated_plugin.get_owned_games()
    backend_client.get_entitlements.assert_called_with(user_id)
    assert result == []

@pytest.mark.asyncio
async def test_own_game(authenticated_plugin, backend_client, user_id):
    backend_client.get_entitlements.return_value = ENTITLEMENTS
    backend_client.get_offer.return_value = OFFER

    result = await authenticated_plugin.get_owned_games()
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

@pytest.mark.asyncio
async def test_access_denied(authenticated_plugin, backend_client, user_id):
    backend_client.get_entitlements.side_effect = [AccessDenied]
    with pytest.raises(AccessDenied):
        await authenticated_plugin.get_owned_games()
    backend_client.get_entitlements.assert_called_with(user_id)

@pytest.mark.asyncio
async def test_cache(authenticated_plugin, backend_client, mocker):
    offer_id_cache = {
        OFFER["offerId"]: OFFER
    }
    mocker.patch.object(
        type(authenticated_plugin),
        "persistent_cache",
        new_callable=mocker.PropertyMock,
        return_value={"offers": offer_id_cache}
    )
    backend_client.get_entitlements.return_value = ENTITLEMENTS
    await authenticated_plugin.get_owned_games()
    backend_client.get_entitlements.assert_called_once()
    backend_client.get_offer.assert_not_called()
