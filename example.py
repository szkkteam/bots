import os
import bots as b
import pytest
from datetime import date

def test_bet_on_team():
    def match_names(name, list_of_names):
        import difflib
        res = difflib.get_close_matches(name, list_of_names, cutoff=0.7)
        if len(res) == 1:
            return list_of_names.index(res[0])
        return None

    def place_bet(l_bot, matches_today):
        def do(home_name, away_name, home_short, away_short):
            from collections import Counter

            home_teams = [team.home for team in matches_today]
            away_teams = [team.away for team in matches_today]

            home_names = list(zip([home_name, home_short], [home_teams, home_teams]))
            away_names = list(zip([away_name, away_short], [away_teams, away_teams]))

            selections = [match_names(name, teams) for name, teams in (home_names + away_names)]
            count = Counter(selections)
            index, frequency = count.most_common(1)[0]

            if frequency >= 2:
                selection = matches_today[index]

                stake = 1
                selection.bet_on('draw', stake=stake)
            else:
                pass

        return do

    firefox = b.utils.ObjectMaker(**b.core.get_firefox_driver(headless=False))
    user = os.environ.get('BOT_USERNAME')
    passw = os.environ.get('BOT_PASSWORD')

    # Perform the login to the site
    bot = b.pinnacle.BettingBot.login(user=user, password=passw, webdriver=firefox)
    # Select the market for betting
    market = bot.select_market(bot.markets.main_market)

    home_name = 'Atletico Madrid'
    home_short = 'Atletico Madrid'
    away_name = 'Real Madrid'
    away_short = 'Real Madrid'

    bot.select_league('laliga')
    matches = bot.select_matches(date=date.today())
    fnc = place_bet(bot, matches)
    fnc(home_name, away_name, home_short, away_short)

    num_of_bets = bot.confirm_bets()
    assert num_of_bets == 1

test_bet_on_team()