__version__ = "0.37"

__changelog__ = {
    "0.37":
    """
        - rename Origin Access [Premium] to EA Play [Pro]
        - fix crash if ProgramData is undefined in Environmental variables (#23 by @NathanaelA)
    """,
    "0.36":
    """
        - better handle installation status of games
        - fix error on retrieving achievements for some games
        - added support for local sizes
    """,
    "0.35":
    """
        - added support for subscriptions
    """,
    "0.34.1":
    """
        - add extended logging to find session expiration time mechanism
    """,
    "0.34":
    """
        - fix rare bug while parsing game times (#16)
        - fix handling status 400 with "login_error": go to "Credentials Lost" instead of "Offline. Retry"
    """
}
