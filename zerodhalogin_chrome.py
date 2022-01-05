# -*- coding: utf-8 -*-
"""
Created on Fri Jul  9 01:28:52 2021

@author: aamir

This module logs in the user into his/her zerodha kite account.
Required files:
    Login credentials: zerodha_credentials.txt
    Access token: access_token.txt
    Request token: request_token.txt

For first login of the day, both access_token.txt and request_token.txt should contain "first login".
"""

from kiteconnect import KiteConnect
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
import time
import urllib.parse as urlparse
import os
import logging
from datetime import datetime
import pyotp


# set working directory and logging file
# use the  commented line to get dir_path instead of os.getcwd() if the module is run in google cloud compute engine.
# dir_path = os.path.dirname(os.path.realpath(__file__))
dir_path = os.getcwd()
logfilename = 'logs_' + datetime.strftime(datetime.now(), '%Y-%m-%d') + '.log'
logfile = os.path.join(dir_path, logfilename)
os.chdir(dir_path)

logging.basicConfig(filename=logfile, format="%(asctime)s %(levelname)s %(message)s", level= logging.DEBUG)
logger = logging.getLogger()



class ZerodhaAccessToken:
    def __init__(self):
        self.logintexts = open('zerodha_credentials.txt', 'r').read().split('\n')
        self.access_token = open("access_token.txt", 'r').read()
        self.request_token = open("request_token.txt", 'r').read()
        self.login_details = self.get_login_details()
        self.api_key = self.login_details['api_key']
        self.api_secret = self.login_details['api_secret']
        self.uid = self.login_details['uid']
        self.pws = self.login_details['pws']
        self.totp_secret = self.login_details['totp']
        self.kite = KiteConnect(api_key=self.api_key)

    def get_login_details(self):
        # read the details in text file to be used for credentials
        readlines = {}
        for line in self.logintexts:
            line = line.split('-')
            readlines[line[0]] = line[1]

        return readlines

    def get_request_token(self):
        # This function returns request token by using login credentials.

        if self.request_token != 'first login':
            return self.request_token
        else:
            logger.info('starting chrome session for login')
            try:
                url_kite = self.kite.login_url()

                # open chrome session
                chrome_options = Options()
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--headless')
                driver = webdriver.Chrome(options=chrome_options)
                # driver = webdriver.Chrome()

                # open url to get the login page
                driver.get(url_kite)

                # wait (Sec) for page to load
                ignored_exceptions = (NoSuchElementException, StaleElementReferenceException,)
                wait = WebDriverWait(driver, 10, ignored_exceptions=ignored_exceptions)

                # enter the id
                wait.until(EC.presence_of_element_located((By.XPATH, '//input[@type="text"]'))) \
                    .send_keys(self.uid)

                # enter the pws
                wait.until(EC.presence_of_element_located((By.XPATH, '//input[@type="password"]'))) \
                    .send_keys(self.pws)

                ## click for submit
                wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]'))) \
                    .submit()

                # enter totp
                # time.sleep(10)
                totp = pyotp.TOTP(self.totp_secret)
                # wait.until(EC.presence_of_element_located((By.XPATH, '//input[@type="password"]'))).click()
                time.sleep(5)
                driver.find_element_by_xpath('//*[@id="totp"]').send_keys(totp.now())

                ## Final Submit
                wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]'))).submit()

                ## wait for redirection
                wait.until(EC.url_contains('status=success'))

                # get the request token from url
                tokenurl = driver.current_url
                parsed = urlparse.urlparse(tokenurl)
                driver.close()
                r_token = urlparse.parse_qs(parsed.query)['request_token'][0]

                # write request token
                with open('request_token.txt', 'w') as file:
                    file.write(r_token)
                    logger.info('request token updated')
                    file.close()

                return r_token

            except Exception as e:
                logger.info(e)
                return None

    def get_access_token(self):
        # this function fetches access token
        # if access token already exists, the same is returned

        if self.access_token != 'first login':
            logger.info("access token already exists!")
            return self.access_token

        # when request token exists, the same is used to generate access token
        # when request token does not exist, login process via chrome is completed.
        try:
            while self.request_token == 'first login':
                self.request_token = self.get_request_token()
                if self.request_token is None:
                    logger.info('error in generating request token')
                    logger.info('login failed')
                    return None

            logger.info('Generating kite session..')
            data = self.kite.generate_session(self.request_token, api_secret=self.api_secret)

            # write the access token in the txt file to be used for rest of the day
            with open("access_token.txt", 'w') as at:
                at.write(data['access_token'])

            logger.info('Access token written..')
            return data['access_token']

        except Exception as e:
            logger.info(e)
            return None


if __name__ == '__main__':
    ztoken = ZerodhaAccessToken()
    access_token = ztoken.get_access_token()
