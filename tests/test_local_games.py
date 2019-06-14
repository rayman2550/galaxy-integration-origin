import pytest
import asyncio
from local_games import LocalGames, get_state_changes
from galaxy.api.types import LocalGame, LocalGameState
from galaxy.api.errors import FailedParsingManifest

def _sorted_games(games):
    return sorted(games, key=lambda x: x.game_id)

@pytest.fixture()
def local_games_object(tmpdir):
    return LocalGames(tmpdir)

def test_not_existent_dir():
    local_games_object = LocalGames("some not-existient directory")
    games, changed = local_games_object.update()
    assert games == []
    assert changed == []

def test_empty(local_games_object):
    games, changed = local_games_object.update()
    assert games == []
    assert changed == []

def test_bad_manifest_format(local_games_object, tmpdir):
    mfst_file = tmpdir.mkdir("GameName").join("gameid.mfst")
    mfst_file.write("?currentstate=kInstalling&previousstate=kPostTransfer")

    with pytest.raises(FailedParsingManifest):
        _, _ = local_games_object.update()

def test_installing(local_games_object, tmpdir):
    mfst_file = tmpdir.mkdir("GameName").join("gameid.mfst")
    mfst_file.write("?currentstate=kInstalling&id=OFB-EAST%3a48217&previousstate=kPostTransfer")

    expected = [
        LocalGame("OFB-EAST:48217", LocalGameState.None_)
    ]

    games, changed = local_games_object.update()
    assert games == expected
    assert changed == expected

def test_installing_dynamic_download(local_games_object, tmpdir):
    mfst_file = tmpdir.mkdir("GameName").join("gameid.mfst")
    mfst_file.write("?currentstate=kTransferring&ddinitialdownload=1&id=Origin.OFR.50.0002694&ddinstallalreadycompleted=0&previousstate=kPendingEula&repairstate=repairing")

    expected = [
        LocalGame("Origin.OFR.50.0002694", LocalGameState.None_)
    ]

    games, changed = local_games_object.update()
    assert games == expected
    assert changed == expected

def test_installed_dynamic_download(local_games_object, tmpdir):
    mfst_file = tmpdir.mkdir("GameName").join("gameid.mfst")
    mfst_file.write("?currentstate=kTransferring&ddinitialdownload=1&id=Origin.OFR.50.0002694&ddinstallalreadycompleted=1&previousstate=kPendingEula&repairstate=")

    expected = [
        LocalGame("Origin.OFR.50.0002694", LocalGameState.Installed)
    ]

    games, changed = local_games_object.update()
    assert games == expected
    assert changed == expected

def test_two_games(local_games_object, tmpdir):
    mfst_file = tmpdir.mkdir("GameName1").join("gameid.mfst")
    mfst_file.write("?currentstate=kReadyToStart&id=OFB-EAST%3a48217&previousstate=kCompleted")
    mfst_file = tmpdir.mkdir("GameName2").join("gameid.mfst")
    mfst_file.write("?currentstate=kReadyToStart&id=DR%3a119971300&previousstate=kCompleted")

    expected = [
        LocalGame("OFB-EAST:48217", LocalGameState.Installed),
        LocalGame("DR:119971300", LocalGameState.Installed)
    ]

    games, changed = local_games_object.update()
    assert _sorted_games(games) == _sorted_games(expected)
    assert _sorted_games(changed) == _sorted_games(expected)

def test_notify_removed(local_games_object, tmpdir):
    mfst_file = tmpdir.mkdir("GameName1").join("gameid.mfst")
    mfst_file.write("?currentstate=kReadyToStart&id=OFB-EAST%3a48217&previousstate=kCompleted")

    local_games_object.update()
    mfst_file.remove()
    games, changed = local_games_object.update()
    assert games == []
    assert changed == [LocalGame("OFB-EAST:48217", LocalGameState.None_)]

def test_notify_changed(local_games_object, tmpdir):
    mfst_file = tmpdir.mkdir("GameName1").join("gameid.mfst")
    mfst_file.write("?currentstate=kInstalling&id=OFB-EAST%3a48217&previousstate=kPostTransfer")

    local_games_object.update()
    mfst_file.write("?currentstate=kReadyToStart&id=OFB-EAST%3a48217&previousstate=kCompleted")
    games, changed = local_games_object.update()
    assert games == [LocalGame("OFB-EAST:48217", LocalGameState.Installed)]
    assert changed == [LocalGame("OFB-EAST:48217", LocalGameState.Installed)]

def test_get_state_changes_added():
    old = []
    new = [LocalGame("1", LocalGameState.Installed)]
    result = [LocalGame("1", LocalGameState.Installed)]
    assert get_state_changes(old, new) == result

def test_get_state_changes_removed():
    old = [LocalGame("1", LocalGameState.Installed)]
    new = []
    result = [LocalGame("1", LocalGameState.None_)]
    assert get_state_changes(old, new) == result

def test_get_state_changes_changed():
    old = [LocalGame("1", LocalGameState.Installed)]
    new = [LocalGame("1", LocalGameState.Running)]
    result = [LocalGame("1", LocalGameState.Running)]
    assert get_state_changes(old, new) == result

def test_get_state_changes_unchanged():
    old = [LocalGame("1", LocalGameState.Installed)]
    new = [LocalGame("1", LocalGameState.Installed)]
    result = []
    assert get_state_changes(old, new) == result

def test_plugin_empty_dir(plugin):
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(plugin.get_local_games())
    assert result == []

def test_plugin_game_installed(tmpdir, plugin):
    mfst_file = tmpdir.mkdir("GameName1").join("gameid.mfst")
    mfst_file.write("?currentstate=kReadyToStart&id=OFB-EAST%3a48217&previousstate=kCompleted")

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(plugin.get_local_games())
    assert result == [LocalGame("OFB-EAST:48217", LocalGameState.Installed)]
