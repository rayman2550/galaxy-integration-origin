import pytest
from galaxy.api.types import SubscriptionGame, Subscription
from galaxy.api.errors import BackendError


SUBSCRIPTION_OWNED_ID = 'Origin Access Premier'
SUBSCRIPTIONS_NOT_OWNED = [Subscription(subscription_name='Origin Access Basic', owned=False, end_time=None),
                          Subscription(subscription_name='Origin Access Premier', owned=False, end_time=None)]
SUBSCRIPTIONS_OWNED = [Subscription(subscription_name='Origin Access Basic', owned=False, end_time=None),
                      Subscription(subscription_name='Origin Access Premier', owned=True, end_time=1581331712)]

SUBSCRIPTIONS_CONTEXT = {'Origin Access Premier': [
    SubscriptionGame(game_title='Mass Effect 3 N7 Digital Deluxe Edition - PC - WW (Origin/3PDD)',
                     game_id='DR:230773600', start_time=None, end_time=None),
    SubscriptionGame(game_title='LEGRAND LEGACY: Tale of the Fatebounds - PC - WW - (Origin)',
                     game_id='Origin.OFR.50.0003727', start_time=None, end_time=None),
    SubscriptionGame(game_title='Mable & the Wood - PC - WW - (Origin)', game_id='Origin.OFR.50.0003777',
                     start_time=None, end_time=None),
    SubscriptionGame(game_title='Worms W.M.D - PC - WW - (Origin)', game_id='Origin.OFR.50.0003802', start_time=None,
                     end_time=None)]}

SUBSCRIPTION_GAMES = [
    SubscriptionGame(game_title='Mass Effect 3 N7 Digital Deluxe Edition - PC - WW (Origin/3PDD)',
                     game_id='DR:230773600', start_time=None, end_time=None),
    SubscriptionGame(game_title='LEGRAND LEGACY: Tale of the Fatebounds - PC - WW - (Origin)',
                     game_id='Origin.OFR.50.0003727', start_time=None, end_time=None),
    SubscriptionGame(game_title='Mable & the Wood - PC - WW - (Origin)', game_id='Origin.OFR.50.0003777',
                     start_time=None, end_time=None),
    SubscriptionGame(game_title='Worms W.M.D - PC - WW - (Origin)', game_id='Origin.OFR.50.0003802', start_time=None,
                     end_time=None)]


@pytest.mark.asyncio
async def test_subscription_not_owned(
        authenticated_plugin,
        backend_client,
):
    backend_client.get_subscriptions.return_value = SUBSCRIPTIONS_NOT_OWNED
    assert SUBSCRIPTIONS_NOT_OWNED == await authenticated_plugin.get_subscriptions()


@pytest.mark.asyncio
async def test_subscription_owned(
        authenticated_plugin,
        backend_client,
):
    backend_client.get_subscriptions.return_value = SUBSCRIPTIONS_OWNED
    assert SUBSCRIPTIONS_OWNED == await authenticated_plugin.get_subscriptions()


@pytest.mark.asyncio
async def test_prepare_subscription_games_context(
        authenticated_plugin,
        backend_client,
):
    backend_client.get_games_in_subscription.return_value = SUBSCRIPTION_GAMES
    assert SUBSCRIPTIONS_CONTEXT == await authenticated_plugin.prepare_subscription_games_context([SUBSCRIPTION_OWNED_ID])


@pytest.mark.asyncio
async def test_prepare_subscription_games_context_error(
        authenticated_plugin,
        backend_client,
):
    backend_client.get_games_in_subscription.side_effect = BackendError()
    with pytest.raises(BackendError):
        await authenticated_plugin.prepare_subscription_games_context([SUBSCRIPTION_OWNED_ID])


@pytest.mark.asyncio
async def test_subscription_games(
        authenticated_plugin,
):
    async for sub_games in authenticated_plugin.get_subscription_games(SUBSCRIPTION_OWNED_ID, SUBSCRIPTIONS_CONTEXT):
        assert sub_games == SUBSCRIPTION_GAMES


