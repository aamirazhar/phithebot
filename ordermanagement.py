# -*- coding: utf-8 -*-
"""
Created on Tue Apr 13 00:46:18 2021

@author: aamir

This module contains custom functions to aid placement and monitoring of orders.
This module also contains some error management to prevent errors while placing orders or to aid understanding of errors.
The functions defined in this module are called in other modules, such as multiprocess_function.py
"""

import zerodhafunctions
import supportfunctions
from datetime import datetime
from time import sleep
import _pickle as pickle
import pytz
import os
import logging


# set working directory and logging file
# use the  commented line to get dir_path instead of os.getcwd() if the module is run in google cloud compute engine.
# dir_path = os.path.dirname(os.path.realpath(__file__))
dir_path = os.getcwd()
logfilename = 'logs_' + datetime.strftime(datetime.now(), '%Y-%m-%d') + '.log'
logfile = os.path.join(dir_path, logfilename)

logging.basicConfig(filename=logfile, format="%(asctime)s %(levelname)s %(message)s", level=logging.DEBUG)
logger = logging.getLogger()

# define ist time zone
IST = pytz.timezone('Asia/Kolkata')


# define function to place orders
def trade(kite, positions, algo, interval, signal_type):
    trading_symbol = positions['tradingsymbol']
    qty = positions['quantity']

    # variables for error management and controls
    place_trade = 1
    n_tries = 0

    # fetch price of the trading symbol for limit order
    # note, this code is for options. Call/Put option is BOUGHT for long/short signal.
    if signal_type == 'SX' or signal_type == 'LX':
        trade_type = kite.TRANSACTION_TYPE_SELL
        price_symbol = zerodhafunctions.get_price(kite, trading_symbol, interval, "sell")
    elif signal_type == 'LE' or signal_type == 'SE':
        trade_type = kite.TRANSACTION_TYPE_BUY
        price_symbol = zerodhafunctions.get_price(kite, trading_symbol, interval, "buy")
    else:
        logger.info('The signal type in the order is not correct. Order is not placed')
        place_trade = 0

    # place order
    while place_trade == 1:
        try:
            trade_id = kite.place_order(variety=kite.VARIETY_REGULAR,
                                        exchange=kite.EXCHANGE_NFO,
                                        tradingsymbol=trading_symbol,
                                        transaction_type=trade_type,
                                        quantity=qty,
                                        product=kite.PRODUCT_NRML,
                                        order_type=kite.ORDER_TYPE_LIMIT,
                                        price=price_symbol,
                                        validity=kite.VALIDITY_DAY)
            # get order details after pausing for 300 millisec
            sleep(0.3)
            place_trade = 0  # to prevent further run of code
            trade_detail = kite.order_history(trade_id)[-1]
            logger.info('order placed. Details of the order:')
            logger.info(trade_detail)

            # amend order_info.txt to reflect closed position
            supportfunctions.writeorderinfo(trade_detail, algo, signal_type)

        except Exception as e:
            logger.info(e)

            # check whether order was placed and response timed out
            logger.info('re-checking if the order was placed')
            sleep(5)
            trade_id = check_order_placement(kite, price_symbol, trading_symbol, trade_type)

            # retry trades if trade_id is none
            if trade_id is None:
                n_tries += 1
                sleep(1)
                # check internet connection
                is_internet = supportfunctions.is_connected()
                if not is_internet and n_tries <= 3:
                    logger.info('Internet connection broken, retrying order in 5 seconds')
                    sleep(5)

                if n_tries > 3:
                    logger.info('Maximum tries exhausted.... proceeding without placing the order')
                    place_trade = 0

            elif trade_id is not None:
                trade_detail = kite.order_history(trade_id)[-1]
                logger.info(trade_detail)
                place_trade = 0

                # amend order_info.txt to reflect closed position
                supportfunctions.writeorderinfo(trade_detail, algo, signal_type)

            else:
                logger.info('unknown error in placing order. check the orderbook. exiting trade module')
                place_trade = 0


# function to check whether order was placed in case it actually was but there was exception due to time out.             
def check_order_placement(kite, price_symbol, trading_symbol, trade_type):
    orders_day = kite.orders()
    if not orders_day:
        logger.info("order was not placed")
        return None

    order_check = orders_day[-1]

    # check time of the order
    time_gap = datetime.now(IST) - order_check['order_timestamp']
    if time_gap.seconds < 60:
        time_check = True
    else:
        time_check = False

    # check price of order
    if order_check['price'] == price_symbol:
        price_check = True
    else:
        price_check = False

    # check symbol of order
    if order_check['tradingsymbol'] == trading_symbol:
        symbol_check = True
    else:
        symbol_check = False

    # check transaction type of order
    if (
            (trade_type == kite.TRANSACTION_TYPE_BUY and order_check['transaction_type'] == 'BUY') or
            (trade_type == kite.TRANSACTION_TYPE_SELL and order_check['transaction_type'] == 'SELL')
    ):
        trade_type_check = True
    else:
        trade_type_check = False

    # see if all checks are true. In that case, the order was placed.
    if time_check and price_check and symbol_check and trade_type_check:
        logger.info('the order was placed')
        trade_id = order_check['order_id']
        return trade_id
    else:
        logger.info('confrimed that the order was not placed')
        return None


# function to check monitor and modify the open trades
def monitor_trade(kite, algo):
    """function to check if open order exists and modify it by updating the price"""

    with open('order_info.txt', 'rb') as file:
        order_info = pickle.load(file)
        file.close()

    for signal_type in ['LE', 'LX', 'SE', 'SX']:
        trade_id = order_info[algo][signal_type]['order_id']
        if order_info[algo][signal_type]['status'] != 'none' and order_info[algo][signal_type]['status'] != 'COMPLETE' and order_info[algo][signal_type]['status'] != 'REJECTED':
            logger.info('{} open order exists, checking details'.format(signal_type))
            trade_details = kite.order_history(trade_id)[-1]

            if trade_details['status'] == 'COMPLETE':
                logger.info('open {} trade for algo {} has been executed. Updating order_info.txt'.format(signal_type, algo))
                supportfunctions.writeorderinfo(trade_details, algo, signal_type)
            else:
                trading_symbol = order_info[algo][signal_type]['tradingsymbol']
                qty = order_info[algo][signal_type]['quantity']
                symbol_fetch = kite.ltp(['NFO:' + str(trading_symbol)])
                symbol_ltp = symbol_fetch['NFO:' + str(trading_symbol)]['last_price']

                if signal_type == 'LE' or signal_type == 'SX':
                    updated_price = symbol_ltp - 0.15
                if signal_type == 'SE' or signal_type == 'LX':
                    updated_price = symbol_ltp + 0.15

                logger.info('Modifying the {} open trade {} for algo {} with price {}.'.format(signal_type, trade_id, algo, updated_price))
                try:
                    updated_trade_id = kite.modify_order(
                        variety=kite.VARIETY_REGULAR,
                        order_id=trade_id,
                        quantity=qty,
                        price=updated_price
                    )

                    sleep(0.3)
                    updated_trade_details = kite.order_history(updated_trade_id)[-1]
                    logger.info('Order modified')
                    logger.info(updated_trade_details)
                    logger.info('writing order info')
                    supportfunctions.writeorderinfo(updated_trade_details, algo, signal_type)
                except:
                    logger.info('order modification failed')
