import pytest
from backend import OriginBackendClient
from galaxy.api.errors import AuthenticationRequired
from galaxy.api.types import Achievement
from unittest.mock import call

OFFER_IDS_NO_ACH = {
    "DR:119971300": None,
    "OFB-EAST:109552409": None,
    "OFB-EAST:48217": None
}
OFFER_IDS_ACH = {
    "Origin.OFR.50.0001672": "50318_194188_50844",
    "OFB-EAST:50885": "50563_52657_50844",
    "DR:225064100": "BF_BF3_PC",
    "Origin.OFR.50.0001452": "193634_192492_50844"
}
OFFER_IDS = dict(OFFER_IDS_NO_ACH, **OFFER_IDS_ACH)

ACHIEVEMENT_SETS_BACKEND_RESPONSE = {
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
    "BF_BF3_PC": {
        "achievements": {
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
        },
        "name": "Battlefield 3™"
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

ACHIEVEMENT_SETS_BACKEND_PARSED = {
    "Origin.OFR.50.0001672": {},
    "OFB-EAST:50885": {
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
    "DR:225064100": {
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
    },
    "Origin.OFR.50.0001452": {
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
    }
}

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


@pytest.fixture
def mock_import_achievements_failure(mocker):
    return mocker.patch("plugin.OriginPlugin.game_achievements_import_failure")


@pytest.fixture
def mock_import_achievements_success(mocker):
    return mocker.patch("plugin.OriginPlugin.game_achievements_import_success")


@pytest.mark.asyncio
async def test_not_authenticated(plugin, http_client, mock_import_achievements_failure):
    http_client.is_authenticated.return_value = False

    with pytest.raises(AuthenticationRequired):
        await plugin.start_achievements_import(OFFER_IDS_NO_ACH.keys())


@pytest.mark.asyncio
async def test_get_achievements(authenticated_plugin, persona_id, backend_client, mock_import_achievements_success):
    backend_client.get_achievements.return_value = ACHIEVEMENT_SETS_BACKEND_PARSED
    backend_client.get_achievements_sets.return_value = OFFER_IDS

    await authenticated_plugin.import_games_achievements(OFFER_IDS.keys())
    backend_client.get_achievements_sets.assert_called_once_with(persona_id)
    backend_client.get_achievements.assert_called_once_with(persona_id, OFFER_IDS_ACH)

    mock_import_achievements_success.assert_has_calls(
        [call(offer_id, ACHIEVEMENTS[offer_id]) for offer_id in OFFER_IDS.keys()],
        any_order=True
    )


# Left for backward compatibility, until feature detection uses transactional methods
@pytest.mark.asyncio
async def test_get_achievements_old(authenticated_plugin, persona_id, backend_client, mock_import_achievements_success):
    offer_id = "OFB-EAST:50885"
    backend_client.get_offer.return_value = {
        "offerId": offer_id,
        "platforms": [{
            "platform": "PCWIN",
            "achievementSetOverride": OFFER_IDS_ACH[offer_id],
        }]
    }
    backend_client.get_achievements.return_value = {offer_id: ACHIEVEMENT_SETS_BACKEND_PARSED[offer_id]}

    assert ACHIEVEMENTS[offer_id] == await authenticated_plugin.get_unlocked_achievements(offer_id)
    backend_client.get_offer.assert_called_once_with(offer_id)

    backend_client.get_achievements.assert_called_once_with(persona_id, {offer_id: OFFER_IDS_ACH[offer_id]})


@pytest.mark.asyncio
async def test_achievements_parsing(pid, http_client, create_json_response):
    http_client.get.return_value = create_json_response(ACHIEVEMENT_SETS_BACKEND_RESPONSE)

    assert ACHIEVEMENT_SETS_BACKEND_PARSED == \
        await OriginBackendClient(http_client).get_achievements(pid, OFFER_IDS_ACH)

    http_client.get.assert_called_once()


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
async def test_achievements_sets_parsing(persona_id, http_client, create_xml_response):
    http_client.get.return_value = create_xml_response(BACKEND_GAMES_RESPONSE)

    assert OFFER_IDS == await OriginBackendClient(http_client).get_achievements_sets(persona_id)

    http_client.get.assert_called_once()
