import pytest
from galaxy.api.errors import AuthenticationRequired
from galaxy.api.types import Achievement

from backend import OriginBackendClient, ProductInfo
from plugin import AchievementsImportContext

OWNED_GAMES_SIMPLE_SIMPLE_ACHIEVEMENTS = {
    "DR:119971300": ProductInfo("DR:119971300", "Need For Speed™ Shift", "54856", None),
    "OFB-EAST:109552409": ProductInfo("OFB-EAST:109552409", "The Sims™ 4", "55482", None),
    "OFB-EAST:48217": ProductInfo("OFB-EAST:48217", "Plants vs. Zombies™ Game of the Year Edition", "180975", None),
    "OFB-EAST:50885": ProductInfo("OFB-EAST:50885", "Dead Space™ 3", "52657", "50563_52657_50844"),
    "Origin.OFR.50.0001672": ProductInfo("Origin.OFR.50.0001672", "THE WITCHER® 3: WILD HUNT", "192492", "50318_194188_50844"),
    "Origin.OFR.50.0001452": ProductInfo("Origin.OFR.50.0001452", "Titanfall® 2", "192492", "193634_192492_50844")
}

OWNED_GAME_SPECIAL_ACHIEVEMENTS = {"DR:225064100": ProductInfo("DR:225064100", "Battlefield 3™", "50182", "BF_BF3_PC")}

OWNED_GAMES = {**OWNED_GAMES_SIMPLE_SIMPLE_ACHIEVEMENTS, **OWNED_GAME_SPECIAL_ACHIEVEMENTS}

ACHIEVEMENTS = {
    "DR:119971300": [],
    "OFB-EAST:109552409": [],
    "OFB-EAST:48217": [],
    "Origin.OFR.50.0001672": [],
    "OFB-EAST:50885": [
        Achievement(1376676315, "1", "Stranger in a Strange Land"),
        Achievement(1376684053, "2", "Space Odyssey"),
        Achievement(1377464844, "3", "Critical Mass"),
        Achievement(1377467003, "4", "Snow Crash"),
        Achievement(1383078508, "5", "Intestinal Fortitude"),
        Achievement(1403554953, "31", "Full House"),
        Achievement(1377897989, "34", "From the Jaws"),
        Achievement(1377459297, "50", "Overpowered Healing")
    ],
    "DR:225064100": [
        Achievement(1371064136, "XP2ACH02_00", "Man of Calibre"),
        Achievement(1362857404, "ACH36_00", "M.I.A"),
        Achievement(1371066037, "XP2ACH01_00", "Dominator"),
        Achievement(1362857404, "ACH33_00", "Support Efficiency"),
    ],
    "Origin.OFR.50.0001452": [
        Achievement(1480870347, "1", "The Student..."),
        Achievement(1480870977, "3", "The Graduate"),
        Achievement(1483373394, "50", "Free Association")
    ]
}

MULTIPLE_ACHIEVEMENTS_SETS_BACKEND_RESPONSE = {
    "50318_194188_50844": {
        "achievements": {},
        "name": "THE WITCHER® 3: WILD HUNT"
    },
    "50563_52657_50844": {
        "achievements": {
            "1": {
                "complete": True,
                "u": 1376676315,
                "name": "Stranger in a Strange Land",
            },
            "2": {
                "complete": True,
                "u": 1376684053,
                "name": "Space Odyssey",
            },
            "3": {
                "complete": True,
                "u": 1377464844,
                "name": "Critical Mass",
            },
            "4": {
                "complete": True,
                "u": 1377467003,
                "name": "Snow Crash",
            },
            "5": {
                "complete": True,
                "u": 1383078508,
                "name": "Intestinal Fortitude",
            },
            "31": {
                "complete": True,
                "u": 1403554953,
                "name": "Full House",
            },
            "34": {
                "complete": True,
                "u": 1377897989,
                "name": "From the Jaws",
            },
            "50": {
                "complete": True,
                "u": 1377459297,
                "name": "Overpowered Healing",
            }
        },
        "name": "Dead Space™ 3"
    },
    "193634_192492_50844": {
        "achievements": {
            "1": {
                "complete": True,
                "u": 1480870347,
                "name": "The Student...",
            },
            "3": {
                "complete": True,
                "u": 1480870977,
                "name": "The Graduate",
            },
            "50": {
                "complete": True,
                "u": 1483373394,
                "name": "Free Association",
            }
        },
        "name": "Titanfall® 2"
    }
}

MULTIPLE_ACHIEVEMENTS_SETS_BACKEND_PARSED = {
    "50318_194188_50844": ACHIEVEMENTS["Origin.OFR.50.0001672"],
    "50563_52657_50844": ACHIEVEMENTS["OFB-EAST:50885"],
    "193634_192492_50844": ACHIEVEMENTS["Origin.OFR.50.0001452"]
}

SINGLE_ACHIEVEMENTS_SET_BACKEND_RESPONSE = {
    "XP2ACH02_00": {
        "complete": True,
        "u": 1371064136,
        "name": "Man of Calibre",
    },
    "ACH36_00": {
        "complete": True,
        "u": 1362857404,
        "name": "M.I.A",
    },
    "XP2ACH01_00": {
        "complete": True,
        "u": 1371066037,
        "name": "Dominator",
    },
    "ACH33_00": {
        "complete": True,
        "u": 1362857404,
        "name": "Support Efficiency",
    }
}

SINGLE_ACHIEVEMENTS_SET_BACKEND_PARSED = {
    "BF_BF3_PC": ACHIEVEMENTS["DR:225064100"]
}

@pytest.mark.asyncio
async def test_not_authenticated(plugin, http_client):
    http_client.is_authenticated.return_value = False

    with pytest.raises(AuthenticationRequired):
        await plugin.prepare_achievements_context(OWNED_GAMES.keys())


@pytest.mark.asyncio
async def test_achievements_context_preparation(
    authenticated_plugin,
    user_id,
    persona_id,
    backend_client
):
    await authenticated_plugin.prepare_achievements_context(OWNED_GAMES.keys())

    backend_client.get_owned_games.assert_called_once_with(user_id)
    backend_client.get_achievements.assert_called_once_with(persona_id)


@pytest.mark.asyncio
async def test_get_unlocked_achievements_simple(
    authenticated_plugin,
    backend_client,
    user_id
):
    for game_id in OWNED_GAMES_SIMPLE_SIMPLE_ACHIEVEMENTS.keys():
        assert ACHIEVEMENTS[game_id] == await authenticated_plugin.get_unlocked_achievements(
            game_id,
            context=AchievementsImportContext(
                owned_games=OWNED_GAMES_SIMPLE_SIMPLE_ACHIEVEMENTS,
                achievements=MULTIPLE_ACHIEVEMENTS_SETS_BACKEND_PARSED
            )
        )

    backend_client.get_achievements.assert_not_called()


@pytest.mark.asyncio
async def test_get_unlocked_achievements_explicit_call(
    authenticated_plugin,
    backend_client,
    persona_id
):
    backend_client.get_achievements.return_value = SINGLE_ACHIEVEMENTS_SET_BACKEND_PARSED

    for game_id in OWNED_GAMES.keys():
        assert ACHIEVEMENTS[game_id] == await authenticated_plugin.get_unlocked_achievements(
            game_id,
            context=AchievementsImportContext(
                owned_games=OWNED_GAMES,
                achievements=MULTIPLE_ACHIEVEMENTS_SETS_BACKEND_PARSED
            )
        )

    backend_client.get_achievements.assert_called_once_with(persona_id, "BF_BF3_PC")


BACKEND_GAMES_RESPONSE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<productInfoList>
    <productInfo>
        <productId>OFB-EAST:48217</productId>
        <displayProductName>Plants vs. Zombies™ Game of the Year Edition</displayProductName>
        <masterTitleId>180975</masterTitleId>
        <gameDistributionSubType>Normal Game</gameDistributionSubType>
    </productInfo>
    <productInfo>
        <productId>DR:119971300</productId>
        <displayProductName>Need For Speed™ Shift</displayProductName>
        <masterTitleId>54856</masterTitleId>
    </productInfo>
    <productInfo>
        <productId>OFB-EAST:109552409</productId>
        <displayProductName>The Sims™ 4</displayProductName>
        <masterTitleId>55482</masterTitleId>
        <gameDistributionSubType>Normal Game</gameDistributionSubType>
    </productInfo>
    <productInfo>
        <productId>DR:225064100</productId>
        <displayProductName>Battlefield 3™</displayProductName>
        <softwareList>
            <software softwarePlatform="PCWIN">
                <achievementSetOverride>BF_BF3_PC</achievementSetOverride>
            </software>
        </softwareList>
        <masterTitleId>50182</masterTitleId>
        <gameDistributionSubType>Normal Game</gameDistributionSubType>
    </productInfo>
    <productInfo>
        <productId>OFB-EAST:50885</productId>
        <displayProductName>Dead Space™ 3</displayProductName>
        <softwareList>
            <software softwarePlatform="PCWIN">
                <achievementSetOverride>50563_52657_50844</achievementSetOverride>
            </software>
        </softwareList>
        <masterTitleId>52657</masterTitleId>
        <gameDistributionSubType>Normal Game</gameDistributionSubType>
    </productInfo>
    <productInfo>
        <productId>Origin.OFR.50.0001452</productId>
        <displayProductName>Titanfall® 2</displayProductName>
        <softwareList>
            <software softwarePlatform="PCWIN">
                <achievementSetOverride>193634_192492_50844</achievementSetOverride>
            </software>
        </softwareList>
        <masterTitleId>192492</masterTitleId>
        <gameDistributionSubType>Normal Game</gameDistributionSubType>
    </productInfo>
    <productInfo>
        <productId>Origin.OFR.50.0001672</productId>
        <displayProductName>THE WITCHER® 3: WILD HUNT</displayProductName>
        <softwareList>
            <software softwarePlatform="PCMAC">
                <achievementSetOverride>50318_194188_50844</achievementSetOverride>
            </software>
        </softwareList>
        <masterTitleId>192492</masterTitleId>
        <gameDistributionSubType>Normal Game</gameDistributionSubType>
    </productInfo>
</productInfoList>
"""


@pytest.mark.asyncio
async def test_owned_games_parsing(persona_id, http_client, create_xml_response):
    http_client.get.return_value = create_xml_response(BACKEND_GAMES_RESPONSE)

    assert OWNED_GAMES == await OriginBackendClient(http_client).get_owned_games(persona_id)

    http_client.get.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend_response, parsed, explicit_set", [
    ({}, {}, None),
    (MULTIPLE_ACHIEVEMENTS_SETS_BACKEND_RESPONSE, MULTIPLE_ACHIEVEMENTS_SETS_BACKEND_PARSED, None),
    (SINGLE_ACHIEVEMENTS_SET_BACKEND_RESPONSE, SINGLE_ACHIEVEMENTS_SET_BACKEND_PARSED, "BF_BF3_PC"),
])
async def test_achievements_parsing(
    backend_response,
    parsed,
    explicit_set,
    http_client,
    user_id,
    create_json_response
):
    http_client.get.return_value = create_json_response(backend_response)

    assert parsed == await OriginBackendClient(http_client).get_achievements(user_id, explicit_set)

    http_client.get.assert_called_once_with(
        "https://achievements.gameservices.ea.com/achievements/personas/{user_id}{specific_set}/all".format(
            user_id=user_id, specific_set="/" + explicit_set if explicit_set else ""
        ),
        params={'lang': 'en_US', 'metadata': 'true'}
    )
