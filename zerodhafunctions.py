# -*- coding: utf-8 -*-
"""
Created on Fri Apr  9 21:27:08 2021

@author: aamir
"""

from datetime import datetime, time, timedelta
import pandas as pd
import os
import math
import pytz
from time import sleep
import logging

# set working directory and logging file
# use the  commented line to get dir_path instead of os.getcwd() if the module is run in google cloud compute engine.
# dir_path = os.path.dirname(os.path.realpath(__file__))
dir_path = os.getcwd()
logfilename = 'logs_' + datetime.strftime(datetime.now(), '%Y-%m-%d') + '.log'
logfile = os.path.join(dir_path, logfilename)

logging.basicConfig(filename=logfile, format="%(asctime)s %(levelname)s %(message)s", level= logging.DEBUG)
logger = logging.getLogger()


#define ist time zone
IST = pytz.timezone('Asia/Kolkata')


# function to fetch historical data of last 100 days
# this historical data would contain the current UNFINISHED candle
def get_historical(kite, token, ndays, interval):
    to_date = datetime.today().strftime('%Y-%m-%d')
    from_date = datetime.strftime(datetime.today() - timedelta(ndays), '%Y-%m-%d')
    records = kite.historical_data(token, from_date = from_date, to_date = to_date, interval = interval)
    df = pd.DataFrame(records)
    return df


def get_price(kite, symbol, interval, order_type):
    """function to determine the price at which limit order should be placed"""

    symbol_fetch = kite.ltp(['NFO:' + str(symbol)])
    symbol_token = symbol_fetch['NFO:' + str(symbol)]['instrument_token']
    symbol_ltp = symbol_fetch['NFO:' + str(symbol)]['last_price']
    
    # do not check previous candle if order is being placed in morning
    # wait for 2 minutes before placing the order
    # the threshold for this cool off time and special placement of order is 9:20
    # after 9:20, the distance between ltp and price for limit order is reduced
    cool_time = time(9, 20, 0)
    
    if interval == '15minute':
        time_threshold = time(9, 30, 0)
    elif interval == '60minute':
        time_threshold = time(10, 15, 0)
    else:
        logger.info('the interval provide is not correct. price retrieval for order placement failed')
        logger.info('order not placed')
        return 0
    
    if datetime.now(IST).time() < cool_time:
        # wait for 1 minute before processing the order.
        sleep(60)
        if order_type == 'buy':
            price_order = math.ceil(10 * 0.97 * symbol_ltp) / 10
        elif order_type == 'sell':
            price_order = math.floor(10 * 1.03 * symbol_ltp) / 10
    elif time_threshold > datetime.now(IST).time() > cool_time:
        if order_type == 'buy':
            price_order = symbol_ltp - 0.20
        elif order_type == 'sell':
            price_order = symbol_ltp + 0.20
    else:
        symbol_hist = get_historical(kite, symbol_token, 2, interval)
        symbol_lastcandle = symbol_hist['close'].iloc[-1]
        if order_type == 'buy':
            price_order = min(symbol_ltp, symbol_lastcandle) - 0.20
        elif order_type == 'sell':
            price_order = max(symbol_ltp, symbol_lastcandle) + 0.20
    
    return price_order


# this function is meant to shortlist the possible list of instruments which will be traded today
# this function should be called in the beginning of code run
# returns a dict whose key is the instrument_token while value is the symbol name of the instrument
# the shortlist of these possible instruments is meant to speed up the process of searching the instrument to place the order
# it is based on NIFTY INDEX

def get_symbol(kite, signal_type, qty, lot_size, boost_status, days_before_expiry):
    """get symbol and quantity of the instrument to place order"""

    # read instruments csv saved in working directory
    instruments = pd.read_csv("instruments.csv")
    
    nifty_ltp = kite.ltp(['NSE:NIFTY 50'])['NSE:NIFTY 50']['last_price']
    
    symbol_qty = 0
    # lower strike price for CE in the money option for long signals, opposite for short
    if signal_type == 'LE':
        strike = 100 * math.floor(nifty_ltp / 100)
        option_type = "CE"
        
        # determine quantity
        symbol_qty = 2 * qty * lot_size if boost_status == 1 else qty * lot_size
            
    elif signal_type == 'SE':
        strike = 100 * math.ceil(nifty_ltp / 100)
        option_type = "PE"
        
        # determine quantity
        symbol_qty = 2 * qty * lot_size if boost_status == -1 else qty * lot_size
        
    expiry = str(datetime.today().strftime('%y%b').upper())
    
    # formulate the symbol as per NSE norms
    symbol = "NIFTY" + expiry + str(strike) + option_type
    
    # using the above symbol, check if the current month expiry is already past or is due in next 4 days
    # if yes, move to next month expiry
    symbolexpiry = instruments[instruments['tradingsymbol'] == symbol]['expiry'].to_list()[0]
    symbolexpiry = datetime.strptime(symbolexpiry, '%d-%m-%Y')
    
    if (symbolexpiry - datetime.today()).days <= days_before_expiry:
        expiry = str((datetime.today() + timedelta(20)).strftime('%y%b').upper())
        # arbitrarily added 20 days to get next month
        symbol = "NIFTY" + expiry + str(strike) + option_type

    symbol_dict = {'tradingsymbol': symbol, 'quantity': symbol_qty}

    return symbol_dict
