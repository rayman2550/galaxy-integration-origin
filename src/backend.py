import logging
import random
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, NewType

import aiohttp
from galaxy.api.errors import (
    AccessDenied, ApplicationError, AuthenticationRequired, BackendError, BackendNotAvailable,
    BackendTimeout, NetworkError, UnknownBackendResponse
)
from galaxy.http import HttpClient
from yarl import URL

MasterTitleId = NewType("MasterTitleId", str)
OfferId = NewType("OfferId", str)
Timestamp = NewType("Timestamp", int)


class CookieJar(aiohttp.CookieJar):
    def __init__(self):
        super().__init__()
        self._cookies_updated_callback = None

    def set_cookies_updated_callback(self, callback):
        self._cookies_updated_callback = callback

    def update_cookies(self, cookies, url=URL()):
        super().update_cookies(cookies, url)
        if cookies and self._cookies_updated_callback:
            self._cookies_updated_callback(list(self))


class AuthenticatedHttpClient(HttpClient):
    def __init__(self):
        self._auth_lost_callback = None
        self._cookie_jar = CookieJar()
        self._access_token = None
        super().__init__(cookie_jar=self._cookie_jar)

    def set_auth_lost_callback(self, callback):
        self._auth_lost_callback = callback

    def set_cookies_updated_callback(self, callback):
        self._cookie_jar.set_cookies_updated_callback(callback)

    async def authenticate(self, cookies):
        self._cookie_jar.update_cookies(cookies)
        await self._get_access_token()

    def is_authenticated(self):
        return self._access_token is not None

    async def get(self, *args, **kwargs):
        if not self._access_token:
            raise AccessDenied("No access token")

        try:
            return await self._authorized_get(*args, **kwargs)
        except (AuthenticationRequired, AccessDenied):
            # Origin backend returns 403 when the auth token expires
            await self._refresh_token()
            return await self._authorized_get(*args, **kwargs)

    async def _authorized_get(self, *args, **kwargs):
        headers = kwargs.setdefault("headers", {})
        headers["Authorization"] = "Bearer {}".format(self._access_token)
        headers["AuthToken"] = self._access_token
        headers["X-AuthToken"] = self._access_token

        return await super().request("GET", *args, **kwargs)

    async def _refresh_token(self):
        try:
            await self._get_access_token()
        except (BackendNotAvailable, BackendTimeout, BackendError, NetworkError):
            logging.warning("Failed to refresh token for independent reasons")
            raise
        except Exception:
            logging.exception("Failed to refresh token")
            self._access_token = None
            if self._auth_lost_callback:
                self._auth_lost_callback()
            raise AccessDenied("Failed to refresh token")

    async def _get_access_token(self):
        url = "https://accounts.ea.com/connect/auth"
        params = {
            "client_id": "ORIGIN_JS_SDK",
            "response_type": "token",
            "redirect_uri": "nucleus:rest",
            "prompt": "none"
        }
        response = await super().request("GET", url, params=params)

        try:
            data = await response.json(content_type=None)
            self._access_token = data["access_token"]
        except (ValueError, KeyError) as e:
            logging.exception("Can not parse access token from backend response")
            raise UnknownBackendResponse(str(e))


class OriginBackendClient:
    def __init__(self, http_client):
        self._http_client = http_client

    @staticmethod
    def _get_api_host():
        return "https://api{}.origin.com".format(random.randint(1, 4))

    async def get_identity(self):
        pid_response = await self._http_client.get(
            "https://gateway.ea.com/proxy/identity/pids/me"
        )
        data = await pid_response.json()
        user_id = data["pid"]["pidId"]

        persona_id_response = await self._http_client.get(
            "{}/atom/users?userIds={}".format(self._get_api_host(), user_id)
        )
        content = await persona_id_response.text()

        try:
            origin_account_info = ET.fromstring(content)
            persona_id = origin_account_info.find("user").find("personaId").text
            user_name = origin_account_info.find("user").find("EAID").text

            return str(user_id), str(persona_id), str(user_name)
        except (ET.ParseError, AttributeError) as e:
            logging.exception("Can not parse backend response: %s", content)
            raise UnknownBackendResponse(str(e))

    async def get_entitlements(self, user_id):
        url = "{}/ecommerce2/consolidatedentitlements/{}?machine_hash=1".format(
            self._get_api_host(),
            user_id
        )
        headers = {
            "Accept": "application/vnd.origin.v3+json; x-cache/force-write"
        }
        response = await self._http_client.get(url, headers=headers)
        try:
            data = await response.json()
            return data["entitlements"]
        except (ValueError, KeyError) as e:
            logging.exception("Can not parse backend response: %s", await response.text())
            raise UnknownBackendResponse(str(e))

    async def get_offer(self, offer_id):
        url = "{}/ecommerce2/public/supercat/{}/{}".format(
            self._get_api_host(),
            offer_id,
            "en_US"
        )
        response = await self._http_client.get(url)
        try:
            return await response.json()
        except ValueError as e:
            logging.exception("Can not parse backend response: %s", await response.text())
            raise UnknownBackendResponse(str(e))

    async def get_achievements(self, persona_id: str, achievement_sets: Dict[OfferId, str]) -> Dict[OfferId, Dict]:
        async def get_sets_data(achievement_set: str = None) -> Dict:
            response = await self._http_client.get(
                "https://achievements.gameservices.ea.com/achievements/personas/{persona_id}{ach_set}/all".format(
                    persona_id=persona_id, ach_set=("/" + achievement_set) if achievement_set else ""
                ),
                params={
                    "lang": "en_US",
                    "metadata": "true"
                }
            )

            '''
            "50317_185353_50844": {
                "platform": "PC Origin",
                "achievements": {"1": {"complete": True, "u": 1376676315, "name": "Stranger in a Strange Land"}},
                "expansions": [{"id": "222", "name": "Prestige and Speedlists"}],
                "name": "Need for Speed™"
            }
            '''
            return await response.json()

        try:
            all_sets = await get_sets_data()

            async def fetch_achievements(achievement_set):
                achievements_set = all_sets.get(achievement_set)
                # for some games(e.g.: ApexLegends) achievement set is not present in "all". have to fetch it explicitly
                if achievements_set is None:
                    return await get_sets_data(achievement_set)

                return achievements_set["achievements"]

            return {
                offer_id: await fetch_achievements(achievement_set)
                for offer_id, achievement_set in achievement_sets.items()
            }

        except ApplicationError:
            raise
        except (KeyError, ValueError) as e:
            logging.exception("Can not parse backend response")
            raise UnknownBackendResponse(str(e))

    async def get_game_time(self, user_id, master_title_id, multiplayer_id):
        url = "{}/atom/users/{}/games/{}/usage".format(
            self._get_api_host(),
            user_id,
            master_title_id
        )

        # 'multiPlayerId' must be used if exists, otherwise '**/lastplayed' backend returns zero
        headers = {}
        if multiplayer_id:
            headers["Multiplayerid"] = multiplayer_id

        response = await self._http_client.get(url, headers=headers)

        """
        response looks like following:
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <usage>
            <gameId>192140</gameId>
            <total>30292</total>
            <MultiplayerId>1024390</MultiplayerId>
            <lastSession>9</lastSession>
            <lastSessionEndTimeStamp>1497190184759</lastSessionEndTimeStamp>
        </usage>
        """
        try:
            content = await response.text()
            xml_response = ET.fromstring(content)
            total_play_time = round(int(xml_response.find("total").text)/60)  # response is in seconds
            last_session_end_time = round(int(xml_response.find("lastSessionEndTimeStamp").text)/1000)  # response is in miliseconds
            return total_play_time, last_session_end_time
        except (ET.ParseError, AttributeError, ValueError) as e:
            logging.exception("Can not parse backend response: %s", await response.text())
            raise UnknownBackendResponse(str(e))

    async def get_friends(self, user_id):
        response = await self._http_client.get(
            "{base_api}/atom/users/{user_id}/other/{other_user_id}/friends?page={page}".format(
                base_api=self._get_api_host(),
                user_id=user_id,
                other_user_id=user_id,
                page=0
            )
        )

        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <users>
            <user>
                <userId>1003118773678</userId>
                <personaId>1781965055</personaId>
                <EAID>martinaurtica</EAID>
            </user>
            <user>
                <userId>1008880909879</userId>
                <personaId>1004303509879</personaId>
                <EAID>testerg976</EAID>
            </user>
        </users>
        """
        try:
            content = await response.text()
            return {
                user_xml.find("userId").text: user_xml.find("EAID").text
                for user_xml in ET.ElementTree(ET.fromstring(content)).iter("user")
            }
        except (ET.ParseError, AttributeError, ValueError):
            logging.exception("Can not parse backend response: %s", await response.text())
            raise UnknownBackendResponse()

    async def get_achievements_sets(self, user_id) -> Dict[OfferId, str]:
        response = await self._http_client.get("{base_api}/atom/users/{user_id}/other/{other_user_id}/games".format(
            base_api=self._get_api_host(),
            user_id=user_id,
            other_user_id=user_id
        ))

        '''
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <productInfoList>
            <productInfo>
                <productId>OFB-EAST:109552153</productId>
                <displayProductName>Battlefield 4™ (Trial)</displayProductName>
                <cdnAssetRoot>http://static.cdn.ea.com/ebisu/u/f/products/1015365</cdnAssetRoot>
                <imageServer>https://Eaassets-a.akamaihd.net/origin-com-store-final-assets-prod</imageServer>
                <packArtSmall>/76889/63.0x89.0/1007968_SB_63x89_en_US_^_2013-11-13-18-04-11_e8670.jpg</packArtSmall>
                <packArtMedium>/76889/142.0x200.0/1007968_MB_142x200_en_US_^_2013-11-13-18-04-08_2ff.jpg</packArtMedium>
                <packArtLarge>/76889/231.0x326.0/1007968_LB_231x326_en_US_^_2013-11-13-18-04-04_18173.jpg</packArtLarge>
                <softwareList>
                    <software softwarePlatform="PCWIN">
                        <achievementSetOverride>51302_76889_50844</achievementSetOverride>
                    </software>
                </softwareList>
                <masterTitleId>76889</masterTitleId>
                <gameDistributionSubType>Limited Trial</gameDistributionSubType>
            </productInfo>
        </productInfoList>
        '''
        try:
            def parse_product_id(product_info_xml):
                return product_info_xml.find("productId").text

            def parse_achievement_set(product_info_xml):
                set_xml = product_info_xml.find(".//softwareList/*/achievementSetOverride")
                if set_xml is None:
                    return None
                return set_xml.text

            content = await response.text()
            return {
                parse_product_id(product_info_xml): parse_achievement_set(product_info_xml)
                for product_info_xml in ET.ElementTree(ET.fromstring(content)).iter("productInfo")
            }
        except (ET.ParseError, AttributeError, ValueError):
            logging.exception("Can not parse backend response: %s", await response.text())
            raise UnknownBackendResponse()

    async def get_lastplayed_games(self, user_id) -> Dict[MasterTitleId, Timestamp]:
        response = await self._http_client.get("{base_api}/atom/users/{user_id}/games/lastplayed".format(
            base_api=self._get_api_host(),
            user_id=user_id
        ))

        '''
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <lastPlayedGames>
            <userId>1008620950926</userId>
            <lastPlayed>
                <masterTitleId>180975</masterTitleId>
                <timestamp>2019-05-17T14:45:48.001Z</timestamp>
            </lastPlayed>
        </lastPlayedGames>
        '''
        try:
            def parse_title_id(product_info_xml) -> MasterTitleId:
                return product_info_xml.find("masterTitleId").text

            def parse_timestamp(product_info_xml) -> Timestamp:
                return Timestamp(int(
                    (
                        datetime.strptime(product_info_xml.find("timestamp").text, "%Y-%m-%dT%H:%M:%S.%fZ")
                        - datetime(1970, 1, 1)
                    ).total_seconds()
                ))

            content = await response.text()
            return {
                parse_title_id(product_info_xml): parse_timestamp(product_info_xml)
                for product_info_xml in ET.ElementTree(ET.fromstring(content)).iter("lastPlayed")
            }
        except (ET.ParseError, AttributeError, ValueError):
            logging.exception("Can not parse backend response: %s", await response.text())
            raise UnknownBackendResponse()
