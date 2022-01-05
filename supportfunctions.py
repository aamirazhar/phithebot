# -*- coding: utf-8 -*-
"""
Created on Mon Apr 12 03:14:33 2021

@author: aamir

This module contains custom functions designed to support the operations.
The functions defined here perform two tasks:
1. writes the order information in appropriate txt file.
2. writes the signal in appropriate file.

The functions defined in this module are called in other modules, such as multiprocess_functions.py, ordermanagement.py
"""

import _pickle as pickle
from datetime import datetime, time
import socket
import pytz
import logging
import os


# set working directory and logging file
# use the  commented line to get dir_path instead of os.getcwd() if the module is run in google cloud compute engine.
# dir_path = os.path.dirname(os.path.realpath(__file__))
dir_path = os.getcwd()
logfilename = 'logs_' + datetime.strftime(datetime.now(), '%Y-%m-%d') + '.log'
logfile = os.path.join(dir_path, logfilename)

logging.basicConfig(filename=logfile, format="%(asctime)s %(levelname)s %(message)s", level= logging.DEBUG)
logger = logging.getLogger()


# define ist time zone
IST = pytz.timezone('Asia/Kolkata')


def writesignal(signal_data, algo):
    """ write signal data in pickle file """

    # read the data stored in pickle
    filename = 'signal_' + algo + datetime.today().strftime('%Y%m%d') + '.pickle'
    if os.path.isfile(filename):
        with open(filename, 'rb') as file:
            existing_signal_data = pickle.load(file)
            file.close()
    else:
        existing_signal_data = {}

    existing_signal_data[datetime.now(IST)] = signal_data

    with open(filename, 'wb') as file:
        pickle.dump(existing_signal_data, file)
        file.close()


def writeorderinfo(kiteorder, algo, signal_type):
    # signal type can be: "LE", "LX", "SE", "SX" and "none"

    sample_order = {'order_id': 'none',
                    'order_type': 'none',
                    'status': 'none',
                    'tradingsymbol': 'none',
                    'instrument_token': 'none',
                    'quantity': 0,
                    'order_time': datetime.now(IST),
                    'execution_time': datetime.now(IST),
                    'signal': 'none'}

    if signal_type == 'LX' or signal_type == 'SX':
        # update the current position with none values if the position has been exited
        closing_signal_type = 'LE' if signal_type == 'LX' else 'SE'

        if kiteorder['status'] == 'COMPLETE':
            with open('order_info.txt', 'rb') as file:
                order_info = pickle.load(file)
                file.close()

            with open('order_info.txt', 'wb') as file:
                order_info[algo][closing_signal_type] = sample_order
                order_info[algo][signal_type] = sample_order
                file.write(pickle.dumps(order_info))
                file.close()
                logger.info(
                    'order info updated. Exit order for algo {algo} completed. No {sig} order for {algo} exists.'.format(
                        algo=algo, sig=closing_signal_type))

        # update the open exit order if exit order is still open
        elif kiteorder['status'] != 'REJECTED':
            exit_order = kiteorder
            with open('order_info.txt', 'rb') as file:
                order_info = pickle.load(file)
                file.close()

            with open('order_info.txt', 'wb') as file:
                order_info[algo][signal_type] = exit_order
                order_info[algo][signal_type]['signal'] = signal_type
                file.write(pickle.dumps(order_info))
                file.close()
                logger.info('order info updated. {} order for algo {} placed.'.format(signal_type, algo))

        # No action if the exit order is rejected. log the info.
        elif kiteorder['status'] == 'REJECTED':
            logger.info('{} exit order info for algo {} is rejected. The entry order remains open.'.format(signal_type, algo))
        else:
            logger.info('order info for algo {} not updated. check for errors.'.format(algo))

    # writing signal for entry order [LE, SE]
    if signal_type == 'LE' or signal_type == 'SE':
        # update the entry order
        entry_order = kiteorder
        with open('order_info.txt', 'rb') as file:
            order_info = pickle.load(file)
            file.close()

        with open('order_info.txt', 'wb') as file:
            order_info[algo][signal_type] = entry_order
            order_info[algo][signal_type]['signal'] = signal_type

            file.write(pickle.dumps(order_info))
            file.close()
            logger.info('order info updated. {} order for algo {} placed.'.format(signal_type, algo))


# function to check internet connection
def is_connected():
    """function to check internet connection"""

    hostname = "one.one.one.one"
    try:
        # see if we can resolve the host name -- tells us if there is
        # a DNS listening
        host = socket.gethostbyname(hostname)
        # connect to the host -- tells us if the host is actually
        # reachable
        s = socket.create_connection((host, 80), 2)
        s.close()
        return True
    except:
        logger.info('Internet down!!!')
    return False
