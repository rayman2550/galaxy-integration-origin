import asyncio
import pytest
from galaxy.api.types import GameTime
from galaxy.api.errors import AuthenticationRequired
from plugin import OriginBackendClient
from unittest.mock import call

# only fields important for the logic are specified

OFFER_IDS = ["Origin.OFR.50.0000941", "OFB-EAST:109551006", "DR:119971300", "Origin.OFR.50.0002694"]
MASTER_TITLE_IDS = ["192140", "190077", "54856", "194908"]
MULTIPLAYER_IDS = ["11", None, None, None]

BACKEND_ENTITLEMENTS_RESPONSE = [{"offerId": offer_id, "offerType": "basegame"} for offer_id in OFFER_IDS]

BACKEND_OFFER_RESPONSES = [{
    "offerId": OFFER_IDS[0],
    "masterTitleId": MASTER_TITLE_IDS[0],
    "platforms": [
        {
            "platform": "PCWIN",
            "multiPlayerId": None # intentionally None
        },
        {
            "platform": "OTHER_PLATFORM",
            "multiPlayerId": MULTIPLAYER_IDS[0]
        }
    ],
    "i18n": {"displayName": "STAR WARS™ Battlefront™"}
}, {
    "offerId": OFFER_IDS[1],
    "masterTitleId": MASTER_TITLE_IDS[1],
    "platforms": [
        {
            "platform": "PCWIN",
            "multiPlayerId": MULTIPLAYER_IDS[1]
        }
    ],
    "i18n": {"displayName": "FIFA World"}
}, {
    "offerId": OFFER_IDS[2],
    "masterTitleId": MASTER_TITLE_IDS[2],
    "platforms": [
        {
            "platform": "PCWIN",
            "multiPlayerId": MULTIPLAYER_IDS[2]
        }
    ],
    "i18n": {"displayName": "Need For Speed™ Shift"}
}, {
    "offerId": OFFER_IDS[3],
    "masterTitleId": MASTER_TITLE_IDS[3],
    "platforms": [
        {
            "platform": "PCWIN",
            "multiPlayerId": MULTIPLAYER_IDS[3]
        },
        {
            "platform": "PCMAC",
            "multiPlayerId": MULTIPLAYER_IDS[3]
        }
    ],
    "i18n": {"displayName": "Apex Legends™"}
}]

BACKEND_GAME_USAGE_RESPONSES = [
    (10, 1451288960),
    (120, 1551288960),
    (120, 1551288960),
    (0, 0)
]

GAME_TIMES = [GameTime(OFFER_IDS[i], *BACKEND_GAME_USAGE_RESPONSES[i]) for i in range(len(OFFER_IDS))]


@pytest.mark.asyncio
async def test_not_authenticated(plugin, http_client):
    http_client.is_authenticated.return_value = False
    with pytest.raises(AuthenticationRequired):
        await plugin.get_game_times()


@pytest.mark.asyncio
async def test_get_game_times_empty_cache(authenticated_plugin, backend_client, user_id):
    backend_client.get_entitlements.return_value = BACKEND_ENTITLEMENTS_RESPONSE
    backend_client.get_lastplayed_games.return_value = {}
    backend_client.get_offer.side_effect = BACKEND_OFFER_RESPONSES
    backend_client.get_game_time.side_effect = BACKEND_GAME_USAGE_RESPONSES

    assert GAME_TIMES == await authenticated_plugin.get_game_times()

    backend_client.get_entitlements.assert_called_once_with(user_id)
    backend_client.get_lastplayed_games.assert_called_once_with(user_id)
    backend_client.get_offer.assert_has_calls([call(offer_id) for offer_id in OFFER_IDS], any_order=True)
    backend_client.get_game_time.assert_has_calls(
        [call(user_id, MASTER_TITLE_IDS[i], MULTIPLAYER_IDS[i]) for i in range(len(OFFER_IDS))],
        any_order=True
    )

BACKEND_LASTPLAYED_RESPONSE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<lastPlayedGames>
    <userId>1008620950926</userId>
    <lastPlayed>
        <masterTitleId>''' + MASTER_TITLE_IDS[1] + '''</masterTitleId>
        <timestamp>2019-05-17T14:45:48.001Z</timestamp>
    </lastPlayed>
    <lastPlayed>
        <masterTitleId>''' + MASTER_TITLE_IDS[0] + '''</masterTitleId>
        <timestamp>2019-04-12T14:00:02.573Z</timestamp>
    </lastPlayed>
    <lastPlayed>
        <masterTitleId>''' + MASTER_TITLE_IDS[2] + '''</masterTitleId>
        <timestamp>2019-02-27T14:55:30.135Z</timestamp>
    </lastPlayed>
</lastPlayedGames>
'''  # intentionally missing MASTER_TITLE_IDS[3]

BACKEND_LASTPLAYED_PARSED = {
    MASTER_TITLE_IDS[0]: 1555077602,
    MASTER_TITLE_IDS[1]: 1558104348,
    MASTER_TITLE_IDS[2]: 1551279330
    # intentionally missing MASTER_TITLE_IDS[3]
}


@pytest.mark.asyncio
async def test_lastplayed_parsing(persona_id, http_client, create_xml_response):
    http_client.get.return_value = create_xml_response(BACKEND_LASTPLAYED_RESPONSE)

    assert BACKEND_LASTPLAYED_PARSED == await OriginBackendClient(http_client).get_lastplayed_games(persona_id)

    http_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_game_times_cached_entries(authenticated_plugin, backend_client, user_id, mocker):
    mocker.patch.object(
        type(authenticated_plugin),
        "persistent_cache",
        new_callable=mocker.PropertyMock,
        return_value={
            "game_time": {game_time.game_id: game_time for game_time in GAME_TIMES}
        }
    )

    new_backend_game_usage_responses = [
        (10, 1451288960),   # same time, no update
        (125, 1551288965),  # newer endtime, updated
        (120, 1551288960),  # missing in new 'last_played' response
        (5, 1551288965)     # previously missing
    ]

    backend_client.get_entitlements.return_value = BACKEND_ENTITLEMENTS_RESPONSE
    backend_client.get_offer.side_effect = BACKEND_OFFER_RESPONSES
    backend_client.get_lastplayed_games.return_value = {
        MASTER_TITLE_IDS[0]: new_backend_game_usage_responses[0][1],
        MASTER_TITLE_IDS[1]: new_backend_game_usage_responses[1][1],
        # MASTER_TITLE_IDS[2] previously existed, now missing
        MASTER_TITLE_IDS[3]: new_backend_game_usage_responses[3][1]
    }
    backend_client.get_game_time.side_effect = new_backend_game_usage_responses[1:]  # updates only

    assert [
        GameTime(offer_id, *response)
        for offer_id, response in zip(OFFER_IDS, new_backend_game_usage_responses)
    ] == await authenticated_plugin.get_game_times()

    backend_client.get_entitlements.assert_called_once_with(user_id)
    backend_client.get_lastplayed_games.assert_called_once_with(user_id)
    backend_client.get_offer.assert_has_calls([call(offer_id) for offer_id in OFFER_IDS], any_order=True)
    backend_client.get_game_time.assert_has_calls(
        [call(user_id, master_title_id, None) for master_title_id in MASTER_TITLE_IDS[1:]],
        any_order=True
    )


@pytest.fixture
def mock_game_time_import_success(mocker):
    return mocker.patch("plugin.OriginPlugin.game_time_import_success")


@pytest.mark.asyncio
async def test_game_time_import_not_authenticated(plugin, http_client):
    http_client.is_authenticated.return_value = False
    with pytest.raises(AuthenticationRequired):
        await plugin.start_game_times_import(OFFER_IDS)


@pytest.mark.asyncio
async def test_game_time_import_cached_entries(
    authenticated_plugin,
    backend_client,
    user_id,
    mock_game_time_import_success,
    mocker
):
    mocker.patch.object(
        type(authenticated_plugin),
        "persistent_cache",
        new_callable=mocker.PropertyMock,
        return_value={
            "game_time": {game_time.game_id: game_time for game_time in GAME_TIMES}
        }
    )

    new_backend_game_usage_responses = [
        (10, 1451288960),  # same time, no update
        (125, 1551288965),  # newer endtime, updated
        (120, 1551288960),  # missing in new 'last_played' response
        (5, 1551288965)  # previously missing
    ]

    backend_client.get_offer.side_effect = BACKEND_OFFER_RESPONSES
    backend_client.get_lastplayed_games.return_value = {
        MASTER_TITLE_IDS[0]: new_backend_game_usage_responses[0][1],
        MASTER_TITLE_IDS[1]: new_backend_game_usage_responses[1][1],
        # MASTER_TITLE_IDS[2] previously existed, now missing
        MASTER_TITLE_IDS[3]: new_backend_game_usage_responses[3][1]
    }
    backend_client.get_game_time.side_effect = new_backend_game_usage_responses[1:]  # updates only

    await authenticated_plugin.start_game_times_import(OFFER_IDS)
    # wait for all `get_game_time` requests to be called
    for i in range(3):
        await asyncio.sleep(0)

    backend_client.get_entitlements.assert_not_called()
    backend_client.get_lastplayed_games.assert_called_once_with(user_id)
    backend_client.get_offer.assert_has_calls([call(offer_id) for offer_id in OFFER_IDS], any_order=True)
    backend_client.get_game_time.assert_has_calls(
        [call(user_id, master_title_id, None) for master_title_id in MASTER_TITLE_IDS[1:]],
        any_order=True
    )
    mock_game_time_import_success.assert_has_calls([
        call(GameTime(offer_id, *response))
        for offer_id, response in zip(OFFER_IDS, new_backend_game_usage_responses)
    ], any_order=True)


@pytest.mark.asyncio
async def test_game_time_import_empty_cache(authenticated_plugin, backend_client, user_id, mock_game_time_import_success):
    backend_client.get_entitlements.return_value = BACKEND_ENTITLEMENTS_RESPONSE
    backend_client.get_lastplayed_games.return_value = BACKEND_LASTPLAYED_PARSED
    backend_client.get_offer.side_effect = BACKEND_OFFER_RESPONSES
    backend_client.get_game_time.side_effect = BACKEND_GAME_USAGE_RESPONSES

    await authenticated_plugin.start_game_times_import(OFFER_IDS)
    # wait for all `get_game_time` requests to be called
    for i in range(3):
        await asyncio.sleep(0)

    backend_client.get_entitlements.assert_not_called()
    backend_client.get_lastplayed_games.assert_called_once_with(user_id)
    backend_client.get_offer.assert_has_calls([call(offer_id) for offer_id in OFFER_IDS], any_order=True)
    backend_client.get_game_time.assert_has_calls(
        [call(user_id, MASTER_TITLE_IDS[i], MULTIPLAYER_IDS[i]) for i in range(len(OFFER_IDS))],
        any_order=True
    )
    mock_game_time_import_success.assert_has_calls([call(game_time) for game_time in GAME_TIMES], any_order=True)
