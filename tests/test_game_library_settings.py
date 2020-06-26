import pytest
from galaxy.api.errors import AuthenticationRequired
from galaxy.api.types import GameLibrarySettings

GAME_IDS = ['DR:119971300', 'OFB-EAST:48217', 'OFB-EAST:109552409', 'Origin.OFR.50.0002694']

BACKEND_HIDDEN_RESPONSE = '''
        <?xml version="1.0" encoding="UTF-8"?>
        <privacySettings>
           <privacySetting>
              <userId>1008620950926</userId>
              <category>HIDDENGAMES</category>
              <payload>Origin.OFR.50.0002694;OFB-EAST:109552409</payload>
           </privacySetting>
        </privacySettings>
'''

BACKEND_FAVORITES_RESPONSE = '''
        <?xml version="1.0" encoding="UTF-8"?>
        <privacySettings>
           <privacySetting>
              <userId>1008620950926</userId>
              <category>FAVORITEGAMES</category>
              <payload>OFB-EAST:48217;OFB-EAST:109552409;DR:119971300</payload>
           </privacySetting>
        </privacySettings>
        '''

FAVORITE_GAMES = {'OFB-EAST:48217', 'OFB-EAST:109552409', 'DR:119971300'}
HIDDEN_GAMES = {'Origin.OFR.50.0002694', 'OFB-EAST:109552409'}

GAME_LIBRARY_CONTEXT = {
    'OFB-EAST:48217': {
        'hidden': False,
        'favorite': True
    },
    'OFB-EAST:109552409': {
        'hidden': True,
        'favorite': True
    },
    'DR:119971300': {
        'hidden': False,
        'favorite': True
    },
    'Origin.OFR.50.0002694': {
        'hidden': True,
        'favorite': False
    }
}

GAME_LIBRARY_SETTINGS = GameLibrarySettings('OFB-EAST:48217', ['favorite'], False)


@pytest.mark.asyncio
async def test_not_authenticated(plugin, http_client):
    http_client.is_authenticated.return_value = False
    with pytest.raises(AuthenticationRequired):
        await plugin.prepare_game_library_settings_context([])


@pytest.mark.asyncio
async def test_prepare_library_settings_context(
        authenticated_plugin,
        backend_client,
        user_id,

):
    backend_client.get_favorite_games.return_value = FAVORITE_GAMES
    backend_client.get_hidden_games.return_value = HIDDEN_GAMES

    assert GAME_LIBRARY_CONTEXT == await authenticated_plugin.prepare_game_library_settings_context(GAME_IDS)

    backend_client.get_favorite_games.assert_called_once_with(user_id)
    backend_client.get_hidden_games.assert_called_once_with(user_id)


@pytest.mark.asyncio
async def test_get_favorite_games(
        backend_client,
        user_id,
        http_client,
):
    http_client.get.return_value = BACKEND_FAVORITES_RESPONSE

    assert FAVORITE_GAMES == await backend_client.get_favorite_games(user_id)


@pytest.mark.asyncio
async def test_get_hidden_games(
        backend_client,
        user_id,
        http_client,
):
    http_client.get.return_value = BACKEND_HIDDEN_RESPONSE

    assert HIDDEN_GAMES == await backend_client.get_hidden_games(user_id)


@pytest.mark.asyncio
async def test_get_game_library_settings(
        authenticated_plugin,
):
    assert GAME_LIBRARY_SETTINGS == await authenticated_plugin.get_game_library_settings('OFB-EAST:48217', GAME_LIBRARY_CONTEXT)



