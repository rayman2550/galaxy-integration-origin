import asyncio
from unittest.mock import patch, MagicMock

import pytest

from plugin import OriginPlugin

from tests.async_mock import AsyncMock

@pytest.fixture()
def pid():
    return 2413515122

@pytest.fixture()
def persona_id():
    return "355295261"

@pytest.fixture()
def access_token():
    return "QVQxOjEuMEozLjA6NjA6akZRTzQ0MVYrRHoyV29SdTFpeHZYbFpzanpZVTVRMWthM4E6MzUyMjI6b2tvOWs"

@pytest.fixture()
def local_games_path(tmpdir):
    with patch("plugin.get_local_content_path") as mock_local_games_path:
        mock_local_games_path.return_value = tmpdir
        yield mock_local_games_path

@pytest.fixture
def http_client(spec=()):
    mock = MagicMock(spec=("set_auth_lost_callback", "set_cookies_updated_callback", "is_authenticated"))
    mock.authenticate = AsyncMock()
    mock.get = AsyncMock()

    return mock

@pytest.fixture
def create_json_response():
    def function(json):
        response = MagicMock()
        response.json = AsyncMock(return_value=json)
        return response

    return function

@pytest.fixture
def create_xml_response():
    def function(text):
        response = MagicMock()
        response.text = AsyncMock(return_value=bytes(text, encoding="utf-8"))
        return response

    return function

@pytest.fixture
def backend_client():
    mock = MagicMock(spec=())
    mock.get_identity = AsyncMock()
    mock.get_offer = AsyncMock()
    mock.get_entitlements = AsyncMock()
    mock.get_game_time = AsyncMock()
    mock.get_achievements = AsyncMock()
    mock.get_achievements_sets = AsyncMock()
    mock.get_friends = AsyncMock()
    mock.get_lastplayed_games = AsyncMock()

    return mock

@pytest.fixture()
def create_plugin(cache, local_games_path, http_client, backend_client):
    def function():
        with patch("plugin.AuthenticatedHttpClient", return_value=http_client):
            with patch("plugin.OriginBackendClient", return_value=backend_client):
                return OriginPlugin(MagicMock(), MagicMock(), None)

    return function

@pytest.fixture()
def plugin(create_plugin):
    return create_plugin()

@pytest.fixture()
def authenticated_plugin(create_plugin, http_client, backend_client, pid, persona_id):
    loop = asyncio.get_event_loop()

    plugin = create_plugin()

    http_client.authenticate.return_value = None
    backend_client.get_identity.return_value = pid, persona_id, "Jan"
    credentials = {
        "cookies": {
            "cookie": "value"
        }
    }
    loop.run_until_complete(plugin.authenticate(credentials))

    return plugin