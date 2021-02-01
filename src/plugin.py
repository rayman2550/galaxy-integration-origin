import asyncio
import pathlib
import json
import logging
import platform
import subprocess
import sys
import time
import webbrowser
from collections import namedtuple
from functools import partial
from typing import Any, Callable, Dict, List, NewType, Optional, AsyncGenerator

from galaxy.api.consts import LicenseType, Platform
from galaxy.api.errors import (
    AccessDenied, AuthenticationRequired, InvalidCredentials, UnknownBackendResponse, UnknownError
)
from galaxy.api.plugin import create_and_run_plugin, Plugin
from galaxy.api.types import (
    Achievement, Authentication, FriendInfo, Game, GameTime, LicenseInfo,
    NextStep, GameLibrarySettings, Subscription, SubscriptionGame
)

from backend import AuthenticatedHttpClient, MasterTitleId, OfferId, OriginBackendClient, Timestamp, AchievementSet
from local_games import get_local_content_path, LocalGames, parse_map_crc_for_total_size
from uri_scheme_handler import is_uri_handler_installed
from version import __version__
import re

def is_windows():
    return platform.system().lower() == "windows"


LOCAL_GAMES_CACHE_VALID_PERIOD = 5
AUTH_PARAMS = {
    "window_title": "Login to Origin",
    "window_width": 495 if is_windows() else 480,
    "window_height": 746 if is_windows() else 708,
    "start_uri": "https://accounts.ea.com/connect/auth"
                 "?response_type=code&client_id=ORIGIN_SPA_ID&display=originXWeb/login"
                 "&locale=en_US&release_type=prod"
                 "&redirect_uri=https://www.origin.com/views/login.html",
    "end_uri_regex": r"^https://www\.origin\.com/views/login\.html.*"
}
def regex_pattern(regex):
    return ".*" + re.escape(regex) + ".*"

JS = {regex_pattern(r"originX/login?execution"): [
r'''
    document.getElementById("rememberMe").click();
'''
]}

MultiplayerId = NewType("MultiplayerId", str)
AchievementsImportContext = namedtuple("AchievementsImportContext", ["owned_games", "achievements"])


class OriginPlugin(Plugin):
    def __init__(self, reader, writer, token):
        super().__init__(Platform.Origin, __version__, reader, writer, token)
        self._user_id = None
        self._persona_id = None

        self._local_games = LocalGames(get_local_content_path())
        self._local_games_last_update = 0
        self._local_games_update_in_progress = False

        def auth_lost():
            self.lost_authentication()

        self._http_client = AuthenticatedHttpClient()
        self._http_client.set_auth_lost_callback(auth_lost)
        self._http_client.set_cookies_updated_callback(self._update_stored_cookies)
        self._backend_client = OriginBackendClient(self._http_client)
        self._persistent_cache_updated = False

    @property
    def _game_time_cache(self) -> Dict[OfferId, GameTime]:
        return self.persistent_cache.setdefault("game_time", {})

    @property
    def _offer_id_cache(self):
        return self.persistent_cache.setdefault("offers", {})

    @property
    def _entitlement_cache(self):
        return self.persistent_cache.setdefault("entitlements", {})

    async def shutdown(self):
        await self._http_client.close()

    def tick(self):
        self.handle_local_game_update_notifications()

    def _check_authenticated(self):
        if not self._http_client.is_authenticated():
            logging.exception("Plugin not authenticated")
            raise AuthenticationRequired()

    async def _do_authenticate(self, cookies):
        try:
            await self._http_client.authenticate(cookies)

            self._user_id, self._persona_id, user_name = await self._backend_client.get_identity()
            return Authentication(self._user_id, user_name)

        except (AccessDenied, InvalidCredentials, AuthenticationRequired) as e:
            logging.exception("Failed to authenticate %s", repr(e))
            raise InvalidCredentials()

    async def authenticate(self, stored_credentials=None):
        stored_cookies = stored_credentials.get("cookies") if stored_credentials else None

        if not stored_cookies:
            return NextStep("web_session", AUTH_PARAMS,js=JS)

        return await self._do_authenticate(stored_cookies)

    async def pass_login_credentials(self, step, credentials, cookies):
        new_cookies = {cookie["name"]: cookie["value"] for cookie in cookies}
        auth_info = await self._do_authenticate(new_cookies)
        self._store_cookies(new_cookies)
        return auth_info

    async def get_owned_games(self):
        self._check_authenticated()

        owned_offers = await self._get_owned_offers()
        games = []
        for offer in owned_offers:
            game = Game(
                offer["offerId"],
                offer["i18n"]["displayName"],
                None,
                LicenseInfo(LicenseType.SinglePurchase, None)
            )
            games.append(game)

        return games

    @staticmethod
    def _get_achievement_set_override(offer) -> Optional[AchievementSet]:
        potential_achievement_set = None
        for achievement_set in offer["platforms"]:
            potential_achievement_set = achievement_set["achievementSetOverride"]
            if achievement_set["platform"] == "PCWIN":
                return potential_achievement_set
        return potential_achievement_set

    async def prepare_achievements_context(self, game_ids: List[str]) -> Any:
        self._check_authenticated()
        owned_offers = await self._get_owned_offers()
        achievement_sets: Dict[OfferId, AchievementSet] = dict()
        for offer in owned_offers:
            achievement_sets[offer["offerId"]] = self._get_achievement_set_override(offer)
        return AchievementsImportContext(
            owned_games=achievement_sets,
            achievements=await self._backend_client.get_achievements(self._persona_id)
        )

    async def get_unlocked_achievements(self, game_id: str, context: AchievementsImportContext) -> List[Achievement]:
        try:
            achievements_set = context.owned_games[game_id]
        except KeyError:
            logging.exception("Game '{}' not found amongst owned".format(game_id))
            raise UnknownBackendResponse()

        if not achievements_set:
            return []

        try:
            # for some games(e.g.: ApexLegends) achievement set is not present in "all". have to fetch it explicitly
            achievements = context.achievements.get(achievements_set)
            if achievements is not None:
                return achievements

            return (await self._backend_client.get_achievements(
                self._persona_id, achievements_set
            ))[achievements_set]

        except KeyError:
            logging.exception("Failed to parse achievements for game {}".format(game_id))
            raise UnknownBackendResponse()

    async def _get_offers(self, offer_ids):
        """
            Get offers from cache if exists.
            Fetch from backend if not and update cache.
        """
        offers = []
        missing_offers = []
        for offer_id in offer_ids:
            offer = self._offer_id_cache.get(offer_id, None)
            if offer is not None:
                offers.append(offer)
            else:
                missing_offers.append(offer_id)

        # request for missing offers
        if missing_offers:
            requests = [self._backend_client.get_offer(offer_id) for offer_id in missing_offers]
            new_offers = await asyncio.gather(*requests, return_exceptions=True)

            for offer in new_offers:
                if isinstance(offer, Exception):
                    logging.error(repr(offer))
                    continue
                offer_id = offer["offerId"]
                offers.append(offer)
                self._offer_id_cache[offer_id] = offer

            self.push_cache()

        return offers

    async def _get_owned_offers(self):
        entitlements = await self._backend_client.get_entitlements(self._user_id)

        for entitlement in entitlements:
            if entitlement['offerId'] not in self._entitlement_cache:
                self._entitlement_cache[entitlement["offerId"]] = entitlement

        # filter
        entitlements = [x for x in entitlements if x["offerType"] == "basegame"]

        # check if we have offers in cache
        offer_ids = [entitlement["offerId"] for entitlement in entitlements]
        return await self._get_offers(offer_ids)

    async def get_subscriptions(self) -> List[Subscription]:
        self._check_authenticated()
        return await self._backend_client.get_subscriptions(user_id=self._user_id)

    async def prepare_subscription_games_context(self, subscription_names: List[str]) -> Any:
        self._check_authenticated()
        subscription_name_to_tier = {
            'EA Play': 'standard',
            'EA Play Pro': 'premium'
        }
        subscriptions = {}
        for sub_name in subscription_names:
            try:
                tier = subscription_name_to_tier[sub_name]
            except KeyError:
                logging.error("Assertion: 'Galaxy passed unknown subscription name %s. This should not happen!", sub_name)
                raise UnknownError(f'Unknown subscription name {sub_name}!')
            subscriptions[sub_name] = await self._backend_client.get_games_in_subscription(tier)
        return subscriptions

    async def get_subscription_games(self, subscription_name: str, context: Any) -> AsyncGenerator[List[SubscriptionGame], None]:
        if context and subscription_name:
            yield context[subscription_name]

    async def get_local_games(self):
        if self._local_games_update_in_progress:
            logging.debug("LocalGames.update in progress, returning cached values")
            return self._local_games.local_games

        loop = asyncio.get_running_loop()
        try:
            self._local_games_update_in_progress = True
            local_games, _ = await loop.run_in_executor(None, partial(LocalGames.update, self._local_games))
            self._local_games_last_update = time.time()
        finally:
            self._local_games_update_in_progress = False
        return local_games

    def handle_local_game_update_notifications(self):
        async def notify_local_games_changed():
            notify_list = []
            try:
                self._local_games_update_in_progress = True
                _, notify_list = await loop.run_in_executor(None, partial(LocalGames.update, self._local_games))
                self._local_games_last_update = time.time()
            finally:
                self._local_games_update_in_progress = False

            for local_game_notify in notify_list:
                self.update_local_game_status(local_game_notify)

        # don't overlap update operations
        if self._local_games_update_in_progress:
            logging.debug("LocalGames.update in progress, skipping cache update")
            return

        if time.time() - self._local_games_last_update < LOCAL_GAMES_CACHE_VALID_PERIOD:
            logging.debug("Local games cache is fresh enough")
            return

        loop = asyncio.get_running_loop()
        asyncio.create_task(notify_local_games_changed())

    async def prepare_local_size_context(self, game_ids) -> Dict[str, pathlib.PurePath]:
        game_id_crc_map = {}
        for filepath, manifest in zip(self._local_games._manifests_stats.keys(), self._local_games._manifests):
            game_id_crc_map[manifest.game_id] = pathlib.PurePath(filepath).parent / 'map.crc'
        return game_id_crc_map

    async def get_local_size(self, game_id, context: Dict[str, pathlib.PurePath]) -> Optional[int]:
        try:
            return parse_map_crc_for_total_size(context[game_id])
        except (KeyError, FileNotFoundError) as e:
            raise UnknownError(f"Manifest for game {game_id} is not found: {repr(e)} | context: {context}")

    @staticmethod
    def _get_multiplayer_id(offer) -> Optional[MultiplayerId]:
        for game_platform in offer["platforms"]:
            multiplayer_id = game_platform["multiPlayerId"]
            if multiplayer_id is not None:
                return multiplayer_id
        return None

    async def _get_game_times_for_offer(
        self,
        offer_id: OfferId,
        master_title_id: MasterTitleId,
        multiplayer_id: Optional[MultiplayerId],
        lastplayed_time: Optional[Timestamp]
    ) -> GameTime:
        # returns None if a new entry should be retrieved
        def get_cached_game_times(_offer_id: OfferId, _lastplayed_time: Optional[Timestamp]) -> Optional[GameTime]:
            if _lastplayed_time is None:
                # double-check if 'lastplayed_time' is unknown (maybe it was just to long ago)
                return None

            _cached_game_time: GameTime = self._game_time_cache.get(offer_id)
            if _cached_game_time is None or _cached_game_time.last_played_time is None:
                # played time unknown yet
                return None
            if _lastplayed_time > _cached_game_time.last_played_time:
                # newer played time available
                return None
            return _cached_game_time

        cached_game_time: Optional[GameTime] = get_cached_game_times(offer_id, lastplayed_time)
        if cached_game_time is not None:
            return cached_game_time

        response = await self._backend_client.get_game_time(self._user_id, master_title_id, multiplayer_id)
        game_time: GameTime = GameTime(offer_id, response[0], response[1])
        self._game_time_cache[offer_id] = game_time
        self._persistent_cache_updated = True
        return game_time

    async def prepare_game_times_context(self, game_ids: List[str]) -> Any:
        self._check_authenticated()

        _, last_played_games = await asyncio.gather(
            self._get_offers(game_ids),  # update local cache ignoring return value
            self._backend_client.get_lastplayed_games(self._user_id)
        )

        return last_played_games

    async def get_game_time(self, game_id: OfferId, last_played_games: Any) -> GameTime:
        try:
            offer = self._offer_id_cache.get(game_id)
            if offer is None:
                logging.exception("Internal cache out of sync")
                raise UnknownError()

            master_title_id: MasterTitleId = offer["masterTitleId"]
            multiplayer_id: Optional[MultiplayerId] = self._get_multiplayer_id(offer)

            return await self._get_game_times_for_offer(
                game_id,
                master_title_id,
                multiplayer_id,
                last_played_games.get(master_title_id)
            )

        except KeyError as e:
            logging.exception("Failed to import game times %s", repr(e))
            raise UnknownBackendResponse()

    async def prepare_game_library_settings_context(self, game_ids: List[str]) -> Any:
        self._check_authenticated()
        hidden_games = await self._backend_client.get_hidden_games(self._user_id)
        favorite_games = await self._backend_client.get_favorite_games(self._user_id)

        library_context = {}
        for game_id in game_ids:
            library_context[game_id] = {'hidden': game_id in hidden_games, 'favorite': game_id in favorite_games}
        return library_context

    async def get_game_library_settings(self, game_id: str, context: Any) -> GameLibrarySettings:
        if not context:
            # Unable to retrieve context
            return GameLibrarySettings(game_id, None, None)
        game_library_settings = context.get(game_id)
        if game_library_settings is None:
            # Able to retrieve context but game is not in its values -> It doesnt have any tags or hidden status set
            return GameLibrarySettings(game_id, [], False)
        return GameLibrarySettings(game_id, ['favorite'] if game_library_settings['favorite'] else [], game_library_settings['hidden'])

    def game_times_import_complete(self):
        if self._persistent_cache_updated:
            self.push_cache()
            self._persistent_cache_updated = False

    async def get_friends(self):
        self._check_authenticated()

        return [
            FriendInfo(user_id=str(user_id), user_name=str(user_name))
            for user_id, user_name in (await self._backend_client.get_friends(self._user_id)).items()
        ]

    async def launch_game(self, game_id):
        if is_uri_handler_installed("origin2"):
            entitlement = self._entitlement_cache.get(game_id, None)
            if entitlement is not None:
                if 'externalType' in entitlement:
                    game_id += '@' + entitlement['externalType'].lower()
            webbrowser.open("origin2://game/launch?offerIds={}&autoDownload=true".format(game_id))
        else:
            webbrowser.open("https://www.origin.com/download")

    async def install_game(self, game_id):
        if is_uri_handler_installed("origin2"):
            webbrowser.open("origin2://game/download?offerId={}".format(game_id))
        else:
            webbrowser.open("https://www.origin.com/download")

    if is_windows():
        async def uninstall_game(self, game_id):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, partial(subprocess.run, ["control", "appwiz.cpl"]))

    async def shutdown_platform_client(self) -> None:
        webbrowser.open("origin://quit")

    def _store_cookies(self, cookies):
        credentials = {
            "cookies": cookies
        }
        self.store_credentials(credentials)

    def _update_stored_cookies(self, morsels):
        cookies = {}
        for morsel in morsels:
            cookies[morsel.key] = morsel.value
        self._store_cookies(cookies)

    def handshake_complete(self):
        def game_time_decoder(cache: Dict) -> Dict[OfferId, GameTime]:
            def parse_last_played_time(entry):
                # old cache might still contains 0 after plugin upgrade
                lpt = entry.get("last_played_time")
                if lpt == 0:
                    return None
                return lpt

            return {
                offer_id: GameTime(entry["game_id"], entry["time_played"], parse_last_played_time(entry))
                for offer_id, entry in cache.items()
                if entry and offer_id
            }

        def safe_decode(_cache: Dict, _key: str, _decoder: Callable):
            if not _cache:
                return {}

            try:
                return _decoder(json.loads(_cache))
            except Exception:
                logging.exception("Failed to decode persistent '%s' cache", _key)
                return {}

        # parse caches
        for key, decoder in (("offers", lambda x: x), ("game_time", game_time_decoder), ("entitlements", lambda x: x)):
            self.persistent_cache[key] = safe_decode(self.persistent_cache.get(key), key, decoder)

        self._http_client.load_lats_from_cache(self.persistent_cache.get('lats'))
        self._http_client.set_save_lats_callback(self._save_lats)

    def _save_lats(self, lats: int):
        self.persistent_cache['lats'] = str(lats)
        self.push_cache()

def main():
    create_and_run_plugin(OriginPlugin, sys.argv)


if __name__ == "__main__":
    main()
