import glob
import logging
import os
import platform
import urllib.parse

if platform.system() == "Windows":
    from ctypes import byref, sizeof, windll, create_unicode_buffer, FormatError, WinError
    from ctypes.wintypes import DWORD

    from typing import Optional, Set, List
else:
    import psutil

from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator, Tuple

from galaxy.api.errors import FailedParsingManifest
from galaxy.api.types import LocalGame, LocalGameState


class _State(Enum):
    kInvalid = auto()
    kError = auto()
    kPaused = auto()
    kPausing = auto()
    kCanceling = auto()
    kReadyToStart = auto()
    kInitializing = auto()
    kResuming = auto()
    kPreTransfer = auto()
    kPendingInstallInfo = auto()
    kPendingEulaLangSelection = auto()
    kPendingEula = auto()
    kEnqueued = auto()
    kTransferring = auto()
    kPendingDiscChange = auto()
    kPostTransfer = auto()
    kMounting = auto()
    kUnmounting = auto()
    kUnpacking = auto()
    kDecrypting = auto()
    kReadyToInstall = auto()
    kPreInstall = auto()
    kInstalling = auto()
    kPostInstall = auto()
    kFetchLicense = auto()
    kCompleted = auto()


@dataclass
class _Manifest:
    game_id: str
    state: _State
    prev_state: _State
    ddinstallalreadycompleted: str
    dipinstallpath: str


def _parse_msft_file(filepath):
    with open(filepath, encoding="utf-8") as file:
        data = file.read()
    parsed_url = urllib.parse.urlparse(data)
    parsed_data = dict(urllib.parse.parse_qsl(parsed_url.query))
    game_id = parsed_data["id"]
    state = _State[parsed_data.get("currentstate", _State.kInvalid.name)]
    prev_state = _State[parsed_data.get("previousstate", _State.kInvalid.name)]
    ddinstallalreadycompleted = parsed_data.get("ddinstallalreadycompleted", "0")
    dipinstallpath = parsed_data.get("dipinstallpath", "")

    return _Manifest(game_id, state, prev_state, ddinstallalreadycompleted, dipinstallpath)


def get_local_games_manifests(manifests_stats):
    manifests = []
    for filename in manifests_stats.keys():
        try:
            manifests.append(_parse_msft_file(filename))
        except Exception as e:
            logging.exception("Failed to parse file {}".format(filename))
            raise FailedParsingManifest({"file": filename, "exception": e})

    return manifests


if platform.system() == "Windows":
    def get_process_info(pid) -> Tuple[int, Optional[str]]:
        _MAX_PATH = 260
        _PROC_QUERY_LIMITED_INFORMATION = 0x1000
        _WIN32_PATH_FORMAT = 0x0000

        h_process = windll.kernel32.OpenProcess(_PROC_QUERY_LIMITED_INFORMATION, False, pid)
        if not h_process:
            return pid, None

        def get_process_file_name() -> Optional[str]:
            try:
                file_name_buffer = create_unicode_buffer(_MAX_PATH)
                file_name_len = DWORD(len(file_name_buffer))

                return file_name_buffer[:file_name_len.value] if windll.kernel32.QueryFullProcessImageNameW(
                    h_process, _WIN32_PATH_FORMAT, file_name_buffer, byref(file_name_len)
                ) else None

            finally:
                windll.kernel32.CloseHandle(h_process)

        return pid, get_process_file_name()


    def get_process_ids() -> Set[int]:
        _PROC_ID_T = DWORD
        list_size = 4096

        def try_get_info_list(list_size) -> Tuple[int, List[int]]:
            result_size = DWORD()
            proc_id_list = (_PROC_ID_T * list_size)()

            if not windll.psapi.EnumProcesses(byref(proc_id_list), sizeof(proc_id_list), byref(result_size)):
                raise WinError(descr="Failed to get process ID list: %s" % FormatError())

            return int(result_size.value / sizeof(_PROC_ID_T())), proc_id_list

        result_count, proc_id_list = try_get_info_list(list_size)
        if result_count > list_size:
            result_count, proc_id_list = try_get_info_list(result_count)

        return set(proc_id_list[:result_count])


    def process_iter() -> Iterator[Tuple[int, str]]:
        try:
            for pid in get_process_ids():
                yield get_process_info(pid)
        except OSError:
            logging.exception("Failed to iterate over the process list")
            pass

else:
    def process_iter() -> Iterator[Tuple[int, str]]:
        for pid in psutil.pids():
            try:
                yield pid, psutil.Process(pid=pid).as_dict(attrs=["exe"])["exe"]
            except psutil.NoSuchProcess:
                pass
            except StopIteration:
                raise
            except Exception:
                logging.exception("Failed to get information for PID=%s" % pid)


def get_local_games_from_manifests(manifests):
    local_games = []

    running_processes = [exe for pid, exe in process_iter() if exe is not None]

    def is_game_running(game_folder_name):
        for exe in running_processes:
            if game_folder_name in exe:
                return True
        return False

    for manifest in manifests:

        state = LocalGameState.None_

        if ((manifest.state == _State.kReadyToStart and manifest.prev_state == _State.kCompleted)
            or manifest.ddinstallalreadycompleted == "1"):
            state |= LocalGameState.Installed

        if manifest.dipinstallpath and is_game_running(manifest.dipinstallpath):
            state |= LocalGameState.Running

        local_games.append(LocalGame(manifest.game_id, state))

    return local_games


def get_local_games_manifest_stats(path):
    path = os.path.abspath(path)
    return {
        filename: os.stat(filename)
        for filename in glob.glob(
            os.path.join(path, "**", "*.mfst"),
            recursive=True
        )
    }


def get_state_changes(old_list, new_list):
    old_dict = {x.game_id: x.local_game_state for x in old_list}
    new_dict = {x.game_id: x.local_game_state for x in new_list}
    result = []
    # removed games
    result.extend(LocalGame(game_id, LocalGameState.None_) for game_id in old_dict.keys() - new_dict.keys())
    # added games
    result.extend(local_game for local_game in new_list if local_game.game_id in new_dict.keys() - old_dict.keys())
    # state changed
    result.extend(
        LocalGame(game_id, new_dict[game_id])
            for game_id in new_dict.keys() & old_dict.keys()
            if new_dict[game_id] != old_dict[game_id]
    )
    return result


def get_local_content_path():
    platform_id = platform.system()

    if platform_id == "Windows":
        local_content_path = os.path.join(os.environ["ProgramData"], "Origin", "LocalContent")
    elif platform_id == "Darwin":
        local_content_path = os.path.join(os.sep, "Library", "Application Support", "Origin", "LocalContent")
    else:
        local_content_path = "."  # fallback for testing on another platform
        # raise NotImplementedError("Not implemented on {}".format(platform_id))

    return local_content_path


class LocalGames:

    def __init__(self, path):
        self._path = path
        self._manifests_stats = get_local_games_manifest_stats(self._path)
        try:
            self._manifests = get_local_games_manifests(self._manifests_stats)
        except FailedParsingManifest as e:
            self._manifests = []
            self._local_games = []
            logging.warning("Failed to parse local games on start: {}, {}".format(e.message, e.data))
            return

        self._local_games = get_local_games_from_manifests(self._manifests)

    @property
    def local_games(self):
        return self._local_games

    def update(self):
        '''
        returns list of changed games (added, removed, or changed)
        updated local_games property
        '''
        new_manifests_stats = get_local_games_manifest_stats(self._path)
        if new_manifests_stats != self._manifests_stats:
            self._manifests_stats = new_manifests_stats
            self._manifests = get_local_games_manifests(self._manifests_stats)

        new_local_games = get_local_games_from_manifests(self._manifests)
        notify_list = get_state_changes(self._local_games, new_local_games)
        self._local_games = new_local_games

        return self._local_games, notify_list
