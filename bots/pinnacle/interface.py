# Common Python library imports
import time as stime
import re
import difflib
import traceback
from datetime import datetime, date, time

# Pip package imports
from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Internal package imports
from bots.core import get_firefox_driver, IBot
from bots.utils import ObjectMaker, Factory


class Struct(object):
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def get(self, key):
        return self.__dict__[key]

class MarketChoice(object):

    def __init__(self, name, parent, *args, **kwargs):
        self._name = name
        self._parent = parent

    def __repr__(self):
        return self.name

    @property
    def name(self):
        return self._name

    def bet_on(self, market_choice, match, stake, **kwargs):
        pass


class MainMarket(MarketChoice):

    HOME_DRAW_AWAY = 1

    market_choices = [ 'home', 'draw', 'away']

    def __init__(self, name, parent, *args, **kwargs):
        super(MainMarket, self).__init__(name, parent, *args, **kwargs)
    def _home_draw_away(self, choice, match):
        all_selection = match.html.find_elements_by_xpath('./div')
        # The 1st element and not the zero is the home-draw-away in this market
        home_draw_away = all_selection[MainMarket.HOME_DRAW_AWAY]
        home_draw_away = home_draw_away.find_elements_by_xpath('./a')
        selected = None
        for selection in home_draw_away:
            assert selection.get_attribute('data-test-state') == 'open', "Selection [%s] is closed currently" % choice
            try:
                if selection.get_attribute('data-test-designation').strip() == choice:
                    selected = selection
                    break
            except Exception as err:
                logger.error(err)

        selected.click()
        stime.sleep(1)
        assert selected is not None, "Selection [%s] cannot be made." % choice
        assert selected.get_attribute('data-selected').strip() == 'true', "Selection [%s] was not recognized" % choice
        return float(selected.text.strip())


    def bet_on(self, market_choice, match, stake, **kwargs):
        market_choice = market_choice.lower()
        assert market_choice in MainMarket.market_choices, "[%s] invalid market choice for [%s]" % (market_choice, self.name)
        if market_choice in ['home', 'draw', 'away']:
            odds = self._home_draw_away(market_choice, match)
        else:
            assert False, "[%s] not implemented" % market_choice
        # Placing the bet
        return self._parent.place_bet(market_choice, match, odds, stake)

    def bet_on_home(self, match, **kwargs):
        return self.bet_on('home', match, **kwargs)

    def bet_on_draw(self, match, **kwargs):
        return self.bet_on('draw', match, **kwargs)

    def bet_on_away(self, match, **kwargs):
        return self.bet_on('away', match, **kwargs)

class NotImplementedMarket(MarketChoice):
    def __init__(self, name):
        super(NotImplementedMarket, self).__init__(name)

market_factory = Factory()
market_factory.RegisterBuilder('main_market', MainMarket)
"""
market_factory.RegisterBuilder('moneyline_match', NotImplementedMarket)
market_factory.RegisterBuilder('handicap_match', NotImplementedMarket)
market_factory.RegisterBuilder('total_match', NotImplementedMarket)
market_factory.RegisterBuilder('team_total_match', NotImplementedMarket)
market_factory.RegisterBuilder('moneyline_1st_half', NotImplementedMarket)
market_factory.RegisterBuilder('handicap_1st_half', NotImplementedMarket)
market_factory.RegisterBuilder('total_1st_half', NotImplementedMarket)
market_factory.RegisterBuilder('team_total_1st_half', NotImplementedMarket)
"""

markets_lookup = {'Main Markets': 'main_market',
                  'Moneyline – Match': 'moneyline_match',
                  'Handicap – Match': 'handicap_match',
                  'Total – Match': 'total_match',
                  'Team Total – Match': 'team_total_match',
                  'Moneyline – 1st Half': 'moneyline_1st_half',
                  'Handicap – 1st Half': 'handicap_1st_half',
                  'Total – 1st Half': 'total_1st_half',
                  'Team Total – 1st Half': 'team_total_1st_half'}

leagues = {
    "premier-league": "sports_nav_favourite_England - Premier League",
    "laliga": "sports_nav_favourite_Spain - La Liga",
    "bundesliga": "sports_nav_favourite_Germany - Bundesliga",
    "serie-a": "sports_nav_favourite_Italy - Serie A",
    "ligue-1": "sports_nav_favourite_France - Ligue 1",
}

def wait_for_element(driver, xpath, timeout=10):
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))

def open_page(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 40).until(EC.presence_of_element_located((By.ID, 'fc_push_frame')))
    except Exception as err:
        tb = traceback.format_exc()
        logger.error(tb)
        raise

def login(driver, user, password):
    try:
        user_input = driver.find_element_by_xpath('//input[@id="username"]')
        password_input = driver.find_element_by_xpath('//input[@id="password"]')
        user_input.clear()
        user_input.send_keys(user)
        password_input.clear()
        password_input.send_keys(password)
        button = driver.find_element_by_xpath('//button[contains(text(), "Log in")]')
        button.click()
        stime.sleep(7)
        WebDriverWait(driver, 40).until(EC.presence_of_element_located((By.ID, 'fc_push_frame')))
    except Exception as err:
        tb = traceback.format_exc()
        logger.error(tb)
        raise

def is_logged_in(driver):
    try:
        button = driver.find_element_by_xpath('//button[contains(text(), "Log in")]')
        return False
    except Exception:
        return True

def open_main_page(driver):
    main_page = "https://www.pinnacle.com/en/"
    open_page(driver, main_page)

def get_bankroll(driver):
    bankroll_xpath = '//span[@data-test-id="QuickCashier-BankRoll"]'
    wait_for_element(driver, bankroll_xpath)
    try:
        bankroll = driver.find_element_by_xpath(bankroll_xpath).text
        bankroll = re.findall(r"(\d+.\d+)", bankroll)[0]
        bankroll = float(bankroll)
    except Exception as err:
        tb = traceback.format_exc()
        logger.error(tb)
        return 0.0
    return bankroll

def get_markets(driver, parent):
    markets_xpath = '//div[contains(@class, "contentBlock")]//ul//li//button'
    wait_for_element(driver, markets_xpath)
    markets = driver.find_elements_by_xpath(markets_xpath)
    enum_dict = {}
    for market in markets:
        market_text = market.text.strip()
        if market_text in markets_lookup:
            market_slug = markets_lookup[market_text]
            try:
                enum_dict[market_slug] = market_factory.Create(market_slug, name=market_text, parent=parent)
                logger.info("Market: %s found and supported." % market_text)
            except AssertionError as err:
                logger.warning("Market: %s is not supported yet" % market_text)
            except Exception as err:
                tb = traceback.format_exc()
                logger.error(tb)
                raise
    return Struct(**enum_dict)

def get_selected_market(driver, markets_dict):
    markets_xpath = '//div[contains(@class, "contentBlock")]//ul//li//button'
    wait_for_element(driver, markets_xpath)
    try:
        markets = driver.find_elements_by_xpath(markets_xpath)
    except Exception as err:
        tb = traceback.format_exc()
        logger.error(tb)
        raise
    else:
        for market in markets:
            try:
                selected = market.get_attribute('data-selected')
            except Exception as err:
                # If attribute not present, thats ok. Only the selected market has it
                continue
            else:
                if selected == 'true':
                    market_text = market.text.strip()
                    slug = markets_lookup[market_text]
                    return markets_dict.get(slug)

def select_market(driver, selection):
    assert isinstance(selection, MarketChoice)
    market_xpath = '//div[contains(@class, "contentBlock")]//ul//li//button'
    wait_for_element(driver, market_xpath)
    markets = driver.find_elements_by_xpath(market_xpath)
    for market in markets:
        if market.text.strip() == selection.name:
            market.click()
            stime.sleep(1)
            return True
    return False

def open_league(driver, league):
    try:
        favorites_xpath = '//div[@data-test-id="LeftSidebar-Favourites"]'
        wait_for_element(driver, favorites_xpath)
        selected_favorites = driver.find_element_by_xpath('//div[@data-test-id="LeftSidebar-Favourites"]//a[@data-gtm-id="%s"]' % leagues[league])
        selected_favorites.click()
        stime.sleep(4)
    except Exception as err:
        tb = traceback.format_exc()
        logger.error(tb)
        raise
    #open_page(driver, leagues[league])

def get_matches_with_dates(driver):
    def convert_date(content):
        from datetime import date,datetime
        try:
            date_txt = content.text.strip()
            if date_txt.lower() == "today":
                return date.today()
            return datetime.strptime(date_txt, "%a, %b %d, %Y").date()
        except Exception:
            return None

    date_evenets_list = []
    actual_date_list = []
    actual_date = None
    content_block_xpath = '//div[@class="contentBlock"]/div[@class="_2n6st"]/div/div'
    wait_for_element(driver, content_block_xpath)
    content_block = driver.find_elements_by_xpath(content_block_xpath)
    for content in content_block:
        attrib = content.get_attribute('data-test-id')
        if "Events.DateBar" == attrib:
            if actual_date is not None:
                date_evenets_list.append( (actual_date, actual_date_list) )
                actual_date_list = []
            actual_date = convert_date(content)
        elif "Event.Row" == attrib:
            actual_date_list.append(content)
    return date_evenets_list

def get_match(curr_date, match):
    try:
        match_xpath  = './/a[@data-test-id="Event.GameInfo"]/div'
        wait_for_element(match, match_xpath)
        elements = match.find_elements_by_xpath(match_xpath)
        s_time = elements[2].text.strip()
        i_time = s_time.split(':')
        return {
            'home': elements[0].text.strip(),
            'away': elements[1].text.strip(),
            'time': datetime.combine(curr_date, time(int(i_time[0]), int(i_time[1]))),
            'match_element': match
        }
    except Exception as err:
        logger.error(err)
        return {}

def get_matches_from_date(selected_date, date_events_list):
    res_list = []
    for curr_date, matches in date_events_list:
        if curr_date == selected_date:
            for match in matches:
                res = get_match(curr_date, match)
                if len(res.keys()) > 0:
                    res_list.append(res)
            return res_list

def get_matches(date_events_list):
    res_list = []
    for curr_date, matches in date_events_list:
        for match in matches:
            res = get_match(curr_date, match)
            if len(res.keys()) > 0:
                res_list.append(res)
        return res_list

def num_of_pending_bets(driver):
    try:
        betslip = driver.find_element_by_xpath('//div[@data-test-id="Betslip"]')
        cards = betslip.find_elements_by_xpath('//div[@data-test-id="Betslip-Card"]')
        return len(cards)
    except Exception:
        return 0

def place_bet(driver, match_info, stake):
    card_xpath = '//div[@data-test-id="Betslip"]//div[@data-test-id="Betslip-Card"]'
    wait_for_element(driver, card_xpath)
    cards = driver.find_elements_by_xpath(card_xpath)

    selected_details = None
    selected_stake_input = None
    for card in cards:
        alt_name = "%s - %s" % (match_info.home, match_info.away)
        details_xpath = './/div[@data-test-id="Betslip-SelectionDetails"]'
        title_xpath = './/div[@data-test-id="SelectionDetails-Title"]'

        wait_for_element(card, details_xpath)
        details = card.find_element_by_xpath(details_xpath)
        wait_for_element(card, title_xpath)
        title = details.find_element_by_xpath(title_xpath).get_attribute('alt').strip()
        if title == alt_name:
            selected_details = details
            selected_stake_input = card.find_element_by_xpath('.//div[@data-test-id="Betslip-StakeWinInput"]')
            break

    assert selected_details is not None and selected_stake_input is not None, "Betting choice is not selected properly"
    stake_input = selected_stake_input.find_element_by_xpath('//div[@data-label="Stake"]/input')
    stake_input.clear()
    stake_input.send_keys(str(stake))
    # Wait 1000 ms before checking
    stime.sleep(1)
    assert stake_input.get_attribute('data-empty') == 'false', "Input stake is not recognized"

    x_button = selected_details.find_element_by_xpath('./button')
    return lambda : x_button.click()

def force_clear_bets(driver):
    try:
        empty = driver.find_element_by_xpath('//div[@data-test-id="betslip-empty"]')
    except Exception:
        # Bet slip is empty
        pass
    else:
        # Bet slip is not empty
        card_xpath = '//div[@data-test-id="Betslip"]//div[@data-test-id="Betslip-Card"]'
        wait_for_element(driver, card_xpath)
        cards = driver.find_elements_by_xpath(card_xpath)
        for card in cards:
            try:
                details_xpath = './/div[@data-test-id="Betslip-SelectionDetails"]'
                wait_for_element(driver, details_xpath)
                details = card.find_element_by_xpath(details_xpath)
                x_button = details.find_element_by_xpath('./button')
                x_button.click()
            except Exception as err:
                logger.error(err)

def get_placed_stakes(driver):
    stakes = 0
    try:
        empty = driver.find_element_by_xpath('//div[@data-test-id="betslip-empty"]')
    except Exception:
        return stakes
    else:
        # Bet slip is not empty
        card_xpath = '//div[@data-test-id="Betslip"]//div[@data-test-id="Betslip-Card"]'
        wait_for_element(driver, card_xpath)
        cards = driver.find_elements_by_xpath(card_xpath)
        for card in cards:
            try:
                stake_input_xpath = './/div[@data-test-id="Betslip-StakeWinInput"]//div[@data-label="Stake"]/input'
                wait_for_element(driver, stake_input_xpath)
                stake_input = card.find_element_by_xpath(stake_input_xpath)
                value = stake_input.get_attribute('value')
                stakes += float(value)
            except Exception as err:
                logger.error(err)
        return stakes

def get_confirmed_bets(driver):
    # Sleep 1.5 sec before checking the button info
    stime.sleep(1.5)
    try:
        button_xpath = '//button[@data-test-id="Betslip-ConfirmBetButton"]'
        wait_for_element(driver, button_xpath)
        button = driver.find_element_by_xpath(button_xpath)
        confirmed_bets = button.text.strip()
        confirmed_bets = re.findall(r"(\d+)", confirmed_bets)
        return int(confirmed_bets[0])
    except Exception as err:
        tb = traceback.format_exc()
        logger.error(tb)
        raise

def confirm_bet(driver):
    try:
        button_xpath = '//button[@data-test-id="Betslip-ConfirmBetButton"]'
        wait_for_element(driver, button_xpath)
        button = driver.find_element_by_xpath(button_xpath)
        button.click()
    except Exception as err:
        tb = traceback.format_exc()
        logger.error(tb)
        raise
    else:
        stime.sleep(10)
