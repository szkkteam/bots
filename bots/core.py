# Common Python library imports
from datetime import date, timedelta
import time

# Pip package imports
from selenium import webdriver
from loguru import logger


DEFAULT_BOT_NAME = "undefined"
DEFAULT_BOT_VERSION = "v0_1"

class IBot(object):

    config = {

    }

    def __init__(self, name=DEFAULT_BOT_NAME, slug=DEFAULT_BOT_NAME, version=DEFAULT_BOT_VERSION, *args,
                 **kwargs):
        self._name = name
        self._slug = slug
        self._version = version

        self._config = { **IBot.config , **kwargs.get('config', {})}

        self._username = kwargs.get('username', "")
        self._password = kwargs.get('password', "")



def get_firefox_driver(**kwargs):
    from selenium.webdriver.firefox.options import Options

    driver_path = kwargs.get('driver_path', "")
    log_path = kwargs.get('log_path', "./webdriver.log")
    options = kwargs.get('options', Options())
    profile = kwargs.get('profile', webdriver.FirefoxProfile())
    options.headless = kwargs.get('headless', False)
    profile.set_preference('intl.accept_languages', 'en')

    args = {
        'service_log_path': log_path,
        'options': options,
        'firefox_profile': profile,
        'class_' : webdriver.Firefox,
    }
    if len(driver_path) > 0:
        args['executable_path'] = driver_path

    return args

def get_chrome_driver(**kwargs):
    from selenium.webdriver.chrome.options import Options

    driver_path = kwargs.get('driver_path', "")
    log_path = kwargs.get('log_path', "./log/webdriver.log")
    options = kwargs.get('options', Options())
    options.headless = kwargs.get('headless', False)

    args = {
        'service_log_path': log_path,
        'options': options,
        'class_': webdriver.Chrome,
    }
    if len(driver_path) > 0:
        args['executable_path'] = driver_path

    return args



