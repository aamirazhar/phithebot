# -*- coding: utf-8 -*-
"""
Created on Fri Jul  9 04:04:04 2021

@author: aamir

This is the main module which kicks off the trade execution algorithm.
This module performs following tasks:
1. Startup - Logs in zerodha kite account.
2. Reads the list of algos (strategies) to run.
3. calls the strategies to at appropriate time for signal processing and execution of trades.
4. Monitors the open trades and modifies them if required.
5. Invalidates the zerodha kite session at the end of trading day.
"""

# import modules
import zerodhalogin_chrome
import multiprocess_functions
import ordermanagement

# import packages
from datetime import datetime, time
from time import sleep
import concurrent.futures
import _pickle as pickle
import os
import pytz
import logging


# set working directory and logging file
# use the  commented line to get dir_path instead of os.getcwd() if the module is run in google cloud compute engine.
# dir_path = os.path.dirname(os.path.realpath(__file__))
dir_path = os.getcwd()
os.chdir(dir_path)

# configure logger
logfilename = 'logs_' + datetime.strftime(datetime.now(), '%Y-%m-%d') + '.log'
logfile = os.path.join(dir_path, logfilename)
logging.basicConfig(filename=logfile, format="%(asctime)s %(levelname)s %(message)s", level=logging.DEBUG)
logger = logging.getLogger()

# set time zone for indian markets
IST = pytz.timezone('Asia/Kolkata')

# define market hour timings
start_time = time(9, 15, 0)
end_time = time(15, 30, 0)


class Startup:
    """
    check open positions
    """

    def __init__(self, kite):
        self.current_time = datetime.time(datetime.now(IST))
        self.time_detail_messege = time(10, 0, 0)
        self.kite = kite

    def open_positions(self):
        """
        This function fetches the orders as per logs and kite.
        It is used to display the current status when the code is first run.
        """

        # logger.info positions open in kite
        current_positions = self.kite.positions()
        logger.info('Open positions in KITE')
        for position in current_positions['net']:
            logger.info('tradingsymbol: {}'.format(position['tradingsymbol']))
            logger.info('quantity: {}'.format(position['quantity']))
            logger.info('last price: {}'.format(position['last_price']))
            logger.info('profit/loss: {}'.format(position['pnl']))
            logger.info('\n')
            sleep(1)

        logger.info('\n')
        logger.info('Open positions in order_info.txt')
        with open('order_info.txt', 'rb') as file:
            order_info = pickle.load(file)
            file.close()

        for algo, order_info_algo in order_info.items():
            for signal_type in ['LE', 'LX', 'SE', 'SX']:
                if order_info_algo[signal_type]['order_id'] == 'none':
                    logger.info('No {} order is open for algo {}\n'.format(signal_type, algo))
                else:
                    logger.info('{} order is open for algo {}:'.format(signal_type, algo))
                    logger.info('order id: {}'.format(order_info_algo[signal_type]['order_id']))
                    logger.info('Instrument: {}'.format(order_info_algo[signal_type]['tradingsymbol']))
                    logger.info('status: {}'.format(order_info_algo[signal_type]['status']))
                    logger.info(
                        'execution time of order: {}'.format(order_info_algo[signal_type]['exchange_update_timestamp']))
                    logger.info('\n')

                if self.current_time < self.time_detail_messege:
                    sleep(1)

        return None


def start_new_day():
    """
    This function is supposed to run when program starts or just before trading begins.
    This function initiates kite session and displays startup message.
    kite object is returned which is used in main code.
    """

    # initiate kite
    # kite is initiated during start of session
    ztoken = zerodhalogin_chrome.ZerodhaAccessToken()
    kite = ztoken.kite
    z_access_token = ztoken.get_access_token()
    print('access token from login: {}'.format(z_access_token))
    kite.set_access_token(access_token=z_access_token)

    # display current positions
    start_day = Startup(kite)
    start_day.open_positions()

    return kite


def read_algo_list():
    """
    This function get the algo list (strategies) to be run as per the input file.
    Returns the algo list.
    """

    with open('algo_list.txt', 'r') as file:
        algo_list = file.read().split('\n')
        algo_list = [eval(x) for x in algo_list]
        file.close()

    for item in algo_list:
        item.update({'kite_obj': kite})

    logger.info('The properties of live algos are: \n')
    for details in algo_list:
        logger.info('{} \n'.format(details))
        sleep(2)

    return algo_list


def invalidate_session(kite):
    """
    This function is meant to invalidate active kite session.
    It re-writes access_token and request_token txt to "first login"
    """
    access_token = open("access_token.txt", 'r').read()
    kite.invalidate_access_token(access_token=access_token)
    logger.info("Kite session ended...")
    with open("access_token.txt", 'w') as file:
        file.write('first login')
        file.close()

    with open("request_token.txt", 'w') as file:
        file.write('first login')
        file.close()

    logger.info('access_token and request_token files set to "first login".\n')
    sleep(2)
    logger.info('Trading ends for the day...')
    logger.info('Al-vida!')


# main body of code
def main():
    """
    The core program which:
        initiates kite instance,
        displays the existing positions
        processes the signals on loop
        places and checks orders
        ends kite session when trading time ends
    """
    global kite
    # call the start_new_day function which completes the login, displays startup message
    # returns the kite object
    if time(8, 30, 0) < datetime.time(datetime.now(IST)) < time(15, 30, 0):
        kite = start_new_day()

        # get the list of algos and its properties to run.
        algo_config = read_algo_list()

    # start trading
    logger.info('Trading commences at {}'.format(datetime.now().strftime("%H:%M:%S")))
    last_run_time = time(0, 0, 0)

    run_on_loop = True
    while run_on_loop:
        # Assign the running of below code every 15 minutes
        # Since the minimum interval being traded is 15 min.
        current_time = datetime.time(datetime.now(IST))

        if time(8, 55, 0) < current_time < start_time:
            # if the code is continuously running, this segment is meant to start new day.
            # it re-logins and gets kite object
            # displays startup message
            # get the list of strategies to run

            if open("access_token.txt", 'r').read() == 'first login':
                # Starting a new day with new login and startup message.
                kite = start_new_day()
                # fetch the list of strategies to be run.
                algo_config = read_algo_list()

        # Prints a message in logger. Used to confirm that the code is running.
        if current_time.second < 2:
            logger.info('The current time is {}. Waiting for appropriate time to process the signal'.format(
                current_time.strftime('%H:%M:%S')))

        if start_time < current_time < end_time:
            repeat_run = current_time.strftime("%H:%M") == last_run_time.strftime("%H:%M")
            # multi processing of signal and order placement for each algo every 15 minutes
            if current_time.minute % 15 == 0 and not repeat_run:
                logger.info('Processing all strategies...')
                last_run_time = current_time

                # Multiprocessing all strategies.
                with concurrent.futures.ProcessPoolExecutor() as executor:
                    executor.map(multiprocess_functions.use_signal, algo_config)

            # check the open orders for modifications in price. This operation is performed every 3 minutes.
            if (
                    current_time.minute > last_run_time.minute and
                    (current_time.minute - last_run_time.minute) % 3 == 0 and
                    current_time.second < 2 and
                    current_time > time(9, 30, 0)
            ):

                for algo in algo_config:
                    algo = algo['algo']
                    logger.info('checking placed orders')
                    # check order status
                    ordermanagement.monitor_trade(kite, algo)

            # sleep for 10 seconds to save memory usage.
            sleep(10 - datetime.now(IST).second % 10)

        elif time(15, 35, 0) < current_time < time(15, 45, 0):
            if open("access_token.txt", 'r').read() != 'first login':
                logger.info('Ending kite session..')
                invalidate_session(kite)
                run_on_loop = False
            sleep(120 - datetime.now(IST).second % 60)
        elif current_time > time(16, 15, 0) or current_time < time(8, 25, 0):
            sleep(1800 - datetime.now(IST).second % 60)
        else:
            sleep(30 - datetime.now(IST).second % 30)


if __name__ == '__main__':
    main()
