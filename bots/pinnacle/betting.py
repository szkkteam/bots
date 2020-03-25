# Common Python library imports
import time
import re
import os
import difflib
from datetime import datetime, date, time

# Pip package imports
from loguru import logger
import pandas as pd

# Internal package imports
from bots.core import get_firefox_driver, IBot
from bots.utils import get_nested, convert_datetime, retry
from bots.pinnacle.interface import *

def match_names(name, list_of_names):
    import difflib
    res = difflib.get_close_matches(name, list_of_names, cutoff=0.7)
    if len(res) == 1:
        return True
    return False

class BettingBot(IBot):

    class MatchSelection(object):

        def __init__(self,parent, home, away, match_date, html_content, *args, **kwargs):
            self._parent = parent
            self.home = home
            self.away = away
            self.date = match_date
            self._content = html_content
            self.cancel_fnc = None

        def __del__(self):
            # TODO: shall we clear if its possible?
            try:
                self.clear()
            except Exception:
                pass

        def __repr__(self):
            return 'At: %s Home: %s - Away: %s' % (self.date, self.home, self.away)

        @property
        def html(self):
            return self._content

        def bet_on(self, market_choice, stake, **kwargs):
            return self._parent.selected_market.bet_on(market_choice, self, stake, **kwargs)

        def clear(self):
            if self.cancel_fnc is not None:
                try:
                    self.cancel_fnc()
                except Exception as err:
                    # Supress the 'element not attached to the DOM' error
                    pass

    name = "Pinnacle Betting Bot"
    slug = "pinnacle-betting-bot"
    version = "v0_1"

    default_config = {
        'default_league': 'bundesliga',
        'mode': 'test',
        'min_stake': 1.0,
        'max_stake': 800.0,
        'max_sum_stake': 9999.0,
        'min_bankroll_percent': 0.4,
        'max_stake_percent': 0.6,
    }

    def __init__(self, driver, *args, **kwargs):
        kwargs['config'] = { **BettingBot.default_config, **kwargs.get('config', {}) }

        m_kwargs = {**{
            'name': BettingBot.name,
            'slug': BettingBot.slug,
            'version': BettingBot.version
        }, **kwargs}

        super(BettingBot, self).__init__(*args, **m_kwargs)

        logger.info("Initializing %s in [%s] mode." % (self.name, self._get_config('mode')))

        self._driver = driver
        # Get the markets
        try:
            self.markets = get_markets(driver, self)
            # Get the selected market
            self.selected_market = get_selected_market(driver, self.markets)
            # Get the current bankroll
            bankroll = get_bankroll(driver)
        except Exception as err:
            logger.error(err)
            raise
        else:
            self._pending_bets = []
            self._placed_bets = pd.DataFrame()
            self._bankroll = bankroll
            self._calculated_bankroll = bankroll
            self._sum_stakes = 0.0
            self._starting_bankroll = bankroll

    def __del__(self):
        try:
            self._driver.close()
        except Exception as err:
            logger.error(err)

    @property
    def placed_bets(self):
        return self._placed_bets

    @property
    def pending_bets(self):
        return self._pending_bets

    @property
    def bankroll(self):
        return self._calculated_bankroll

    @staticmethod
    @retry(Exception, tries=3, delay=2, backoff=4, logger=logger)
    def login(user, password, webdriver, **kwargs):

        # Get the keys from environment variables
        user = os.getenv('PINNACLE_USER', user)
        password = os.getenv('PINNACLE_PASSWORD', password)

        # Init webdriver
        driver = webdriver()
        try:
            # Open the main page
            logger.debug('Opening main page.')
            open_main_page(driver)
            # Perform login
            logger.debug('Logging in.')
            login(driver, user=user, password=password)
            # Open the default league page
            open_league(driver, kwargs.get('league', 'bundesliga'))
            # Make sure we are still logged in
            assert is_logged_in(driver), "Something went wrong after login. The website is logged off."
        except Exception as err:
            logger.error(err)
            driver.close()
            raise
        else:
            return BettingBot(driver, username=user, password=password, **kwargs)


    def close(self):
        if self._driver is not None:
            try:
                logger.debug('Closing the webdriver.')
                self._driver.close()
            except Exception as err:
                logger.error(err)

    @retry(ConnectionError, tries=3, delay=5, backoff=2)
    def select_league(self, league):
        assert self._driver is not None, "webdriver is not opened."
        try:
            if not is_logged_in(self._driver):
                uname = self._username
                pwd = self._password
                logger.debug('Trying to log in ...')
                login(self._driver, user=uname, password=pwd)

            logger.debug('Opening league [%s].' % league)
            open_league(self._driver, league)
        except Exception as err:
            logger.error(err)
            raise
        else:
            # Check login
            if not is_logged_in(self._driver):
                logger.warning("Something went wrong after login. The website is logged off.")
                raise ConnectionError
            logger.info("League: [%s] selected." % league)


    def select_market(self, market):
        assert self._driver is not None, "webdriver is not opened."
        logger.debug('Selecting market [%s].' % market)
        if self.selected_market != market:
            assert select_market(self._driver, market), "The market was not selected."
            logger.info("Market [%s] selected." % market)
        return self.selected_market

    def select_matches(self, **kwargs):
        assert self._driver is not None, "webdriver is not opened."
        result_list = []
        selected_date = kwargs.get('date', None)
        home = kwargs.get('home', None)
        away = kwargs.get('away', None)
        name_matcher = kwargs.get('match_names', match_names)

        all_matches = get_matches_with_dates(self._driver)
        if selected_date is None and home is None and away is None:
            matches = get_matches(all_matches)
        elif selected_date is not None:
            if home is not None or away is not None:
                matches = self._select_matches_by_date_name(selected_date, home, away, all_matches, name_matcher)
            else:
                matches = self._select_matches_by_date(selected_date, all_matches)
        else:
            matches = self._select_matches_by_name(home, away, all_matches, name_matcher)

        for match in matches:
            result_list.append( BettingBot.MatchSelection(self,
                                               home=match['home'],
                                               away=match['away'],
                                               match_date=match['time'],
                                               html_content=match['match_element']) )

        logger.debug('For Date: [%s] Home: [%s] Away: [%s] - [%s] of match found.' % (selected_date, home, away, len(result_list)))
        return result_list

    def place_bet(self, market_choice, match_info, odds, stake):
        assert self._driver is not None, "webdriver is not opened."
        assert self._sum_stakes + stake < self._get_config('max_sum_stake'), "Maximum sum of stakes reached. Change the config if you want to contine"
        bankroll_percent = self._calculated_bankroll / self._starting_bankroll
        assert bankroll_percent > self._get_config('min_bankroll_percent'), "The minimum percentage of the bankroll is reached. Change the config if you want to contine"

        try:
            if self._get_config('mode') == 'live':
                max_stake = self._calculated_bankroll * self._get_config('max_stake_percent')
                stake = min(stake, max_stake)
                # Calculate the min/max stake
                stake = min(self._get_config('max_stake'), max(self._get_config('min_stake'), stake))
                match_info.cancel_fnc = place_bet(self._driver, match_info, stake)
            else:
                match_info.cancel_fnc = place_bet(self._driver, match_info, stake)

            logger.info('Bet placed %s with Stake: [%s] Odds: [%s]' % (str(match_info), stake, odds))
            # Store the placed bets
            self._placed_bets = self._placed_bets.append({
                'time': match_info.date,
                'home': match_info.home,
                'away': match_info.away,
                'stake': stake,
                'odds': odds,
                'choice': market_choice
            }, ignore_index=True)
            # Append the pending bets
            self._pending_bets.append({
                'market': market_choice,
                'match': match_info,
                'odds': odds,
                'stake': stake
            })
            self._sum_stakes += stake
            self._calculated_bankroll -= stake
        except Exception as err:
            logger.error(err)
            raise

    def clear_bets(self):
        try:
            for match_info in self._pending_bets:
                match = match_info['match']
                logger.debug("Clearing bet for: %s" % str(match))
                match.clear()
            self._pending_bets = []
        except Exception as err:
            logger.error(err)
        try:
            # Try to force clear all pending bets.
            logger.debug("Force clearing bets.")
            force_clear_bets(self._driver)
        except Exception as err:
            # Here everything is okay, probably the bets are already cleared
            pass


    def confirm_bets(self):
        assert self._driver is not None, "webdriver is not opened."
        calculated_peding_bets = len(self._pending_bets)
        number_of_bets = 0
        if calculated_peding_bets == 0:
            logger.info("There are no pending bets. Clearing Betslip")
            self.clear_bets()
            return number_of_bets

        try:
            confirmed_bets = get_confirmed_bets(self._driver)
            pending_bets = num_of_pending_bets(self._driver)
        except Exception as err:
            logger.error(err)
            raise
        else:
            # The number of placed bets has to be match exactly
            assert confirmed_bets == pending_bets == calculated_peding_bets, "Bets are not placed correctly. There is a mismatch in the number of bets. [Confirmed: %s], [Pending: %s], [Calculated: %s]" % (confirmed_bets, pending_bets, calculated_peding_bets)
            number_of_bets = pending_bets
            try:
                mode = self._get_config('mode')
                if mode == 'live':
                    confirm_bet(self._driver)
                else:
                    pass
                logger.info('[%s] Bets are placed correctly.' % mode)
                self.clear_bets()
            except Exception as err:
                logger.error(err)
        finally:
            bankroll = get_bankroll(self._driver)
            self._bankroll = bankroll
            logger.info("New bankroll: [%s]" % bankroll)
            if abs(self._calculated_bankroll - self._bankroll) > 1.0:
                logger.warning("Real and calculated bankrolls are different. [%s] - [%s]" % (self._calculated_bankroll, self._bankroll))
            self._calculated_bankroll = bankroll
        return number_of_bets

    def _select_matches_by_date(self, selected_date, event_date_list):
        selected_date = convert_datetime(selected_date)
        for curr_date, matches in event_date_list:
            if curr_date == selected_date:
                return [ get_match(curr_date, match) for match in matches ]
        return []

    def _select_matches_by_name(self, home, away, event_date_list, matcher):
        res_list = []
        for curr_date, matches in event_date_list:
            for match in matches:
                details = get_match(curr_date, match)
                if home is not None and away is not None:
                    if matcher(home, details['home']) and matcher(away, details['away']):
                        res_list.append(details)
                elif home is not None:
                    if matcher(home, details['home']):
                        res_list.append(details)
                else:
                    if matcher(away, details['away']):
                        res_list.append(details)
        return res_list

    def _select_matches_by_date_name(self, selected_date, home, away, event_date_list, matcher):
        res_list = []
        selected_date = convert_datetime(selected_date)
        for curr_date, matches in event_date_list:
            if curr_date == selected_date:
                for match in matches:
                    details = get_match(curr_date, match)
                    if home is not None and away is not None:
                        if matcher(home, details['home']) and matcher(away, details['away']):
                            res_list.append(details)
                    elif home is not None:
                        if matcher(home, details['home']):
                            res_list.append(details)
                    else:
                        if matcher(away, details['away']):
                            res_list.append(details)
            return res_list


    def _get_config(self, *args):
        return get_nested(self._config, *args)