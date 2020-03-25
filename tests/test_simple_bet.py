import os
import bots as b
import pytest
from datetime import date

def test_simple_bet_one_league():
    firefox = b.utils.ObjectMaker(**b.core.get_firefox_driver(headless=True))
    user = os.environ.get('BOT_USERNAME')
    passw = os.environ.get('BOT_PASSWORD')

    # Perform the login to the site
    bot = b.pinnacle.BettingBot.login(user=user, password=passw, webdriver=firefox)
    # Select the market for betting
    market = bot.select_market(bot.markets.main_market)
    # Select match(es)
    matches = bot.select_matches(date=date.today())

    if len(matches) > 0:
        match = matches[0]
        stake = 1
        # Bet on this match
        market.bet_on('draw', match, stake=stake)
        # Confirm the bet
        num_of_bets = bot.confirm_bets()
        assert num_of_bets == 1


def test_switch_leagues():
    firefox = b.utils.ObjectMaker(**b.core.get_firefox_driver(headless=True))
    user = os.environ.get('BOT_USERNAME')
    passw = os.environ.get('BOT_PASSWORD')
    # Perform the login to the site
    bot = b.pinnacle.BettingBot.login(user=user, password=passw, webdriver=firefox)

    leagues = [
        "premier-league", "laliga", "bundesliga", "serie-a", "ligue-1"
    ]
    for league in leagues:
        # Select the league
        bot.select_league(league)

