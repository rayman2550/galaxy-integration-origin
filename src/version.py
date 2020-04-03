__version__ = "0.35"

__changelog__ = {
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