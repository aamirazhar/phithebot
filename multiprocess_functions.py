"""
This module contains functions that are called in main_chrome.py for multiprocessing.
The purpose of this module is:
1. Fetch historical data
2. Call the strategy for signal processing at appropriate time as per the configuration of the strategy in algo_list.txt file.
3. Send entry/exit orders as per the generated signal.
4. Write the signals and orders in respective txt/pickle files for the record.
"""

# Import modules
import zerodhafunctions
import supportfunctions
import ordermanagement

# Import strategies
import market_tracker_15m
import long_rider_15m

# Import required packages
from datetime import datetime, time
from time import sleep
import _pickle as pickle
import logging
import os
import pytz

# set working directory and logging file
# use the  commented line to get dir_path instead of os.getcwd() if the module is run in google cloud compute engine.
# dir_path = os.path.dirname(os.path.realpath(__file__))
dir_path = os.getcwd()
os.chdir(dir_path)

logfilename = 'logs_' + datetime.strftime(datetime.now(), '%Y-%m-%d') + '.log'
logfile = os.path.join(dir_path, logfilename)

logging.basicConfig(filename=logfile, format="%(asctime)s %(levelname)s %(message)s", level=logging.DEBUG)
logger = logging.getLogger()

# set time zone for indian markets
IST = pytz.timezone('Asia/Kolkata')

# define market hour timings
start_time = time(9, 15, 0)
end_time = time(15, 30, 0)

# dict for signal type
signal_text = {'LE': 'long signal', 'LX': 'exit long', 'SE': 'short signal', 'SX': 'exit short'}

# True for debug mode. debug mode fetches the data at all times.
# False for normal run, fetches data only at appropriate interval as per configuration in algo_list.txt.
isdebug = False


class RunAlgo:
    """This class is designed as general algorithm executor.
    checks if time is right for algo run.
    retrieves historical data as per interval.
    processes the signal."""

    def __init__(self, algo, interval, security):
        self.current_time = datetime.time(datetime.now(IST))
        self.algo = algo
        self.interval = interval
        self.security = security

    def is_run_time(self):
        # this function checks if the current time is appropriate to run the algo

        # check if the time is within market hours
        if self.current_time < start_time or self.current_time > end_time:
            return False

        # check if the time is to kick off signal processing
        # include other relevant intervals if the strategies are configured for different candles.
        # the text of the intervals are possible values as defined by zerodha
        if self.interval == '15minute':
            run = self.current_time.minute % 15 == 0
            return run

        if self.interval == '60minute':
            run = self.current_time.minute == 15
            return run

        # returns false if no conditions are met
        return False

    def signal_processing(self):
        # this function processes signal
        # fetches data using retrieve data method

        if self.is_run_time() or isdebug:
            hist_data = self.retrieve_data()

            if hist_data is None:
                logger.info('Issues in retrieving historical data. check for errors.\n')
                return None
            else:
                logger.info('processing signal for algo {}.'.format(self.algo))

                # the below component should contain all the strategies configured in algo_list.txt file.
                # in order to include a new strategy, it should be added in below lines.
                if self.algo == 'market_tracker_15m':
                    signal = market_tracker_15m.signal(hist_data)
                    signal = signal.iloc[50:]
                elif self.algo == 'long_rider_15m':
                    signal = long_rider_15m.signal(hist_data)
                    signal = signal.iloc[50:]
                else:
                    logger.info('algo {} is not configured in RunAlgo class'.format(self.algo))
                    return None

                # store the data. the data is appended in pickle file using writesignal function.
                supportfunctions.writesignal(signal, self.algo)

                # get the latest signal
                latest_signal = signal.iloc[-1]
                logger.info(latest_signal)
                return latest_signal
        else:
            return None

    def retrieve_data(self):
        # this function retrieves historical data of given security when isruntime is true

        logger.info('retrieving historical data for algo {} and time interval {}.'.format(self.algo, self.interval))

        # get instrument token as per the security
        security_ltp = kite.ltp([self.security])
        security_token = security_ltp[self.security]['instrument_token']

        # wait for few sec before getting data to ensure full candle is retrieved.
        sleep(1.5)

        hist_data = zerodhafunctions.get_historical(kite, security_token, 25, self.interval)

        # drop the latest candle which has just begun
        # this is to ensure analysis on the candle which was just completed
        if hist_data['date'].iloc[-1].strftime("%H:%M") == self.current_time.strftime("%H:%M"):
            hist_data = hist_data[:-1]

        logger.info('Data retrieved...')
        return hist_data

    def entry_order(self, signal):
        # check signal_type of entry order, if any
        if signal['long_signal'] == 'LE':
            return signal['long_signal']
        elif signal['short_signal'] == 'SE':
            return signal['short_signal']
        else:
            return None

    def is_entry_order(self, signal):
        # check if entry order exists
        if self.entry_order(signal) is not None:
            return True
        else:
            return False

    def exit_order(self, signal):
        # check signal_type of exit order, if any
        if signal['long_signal'] == 'LX':
            return signal['long_signal']
        elif signal['short_signal'] == 'SX':
            return signal['short_signal']
        else:
            return None

    def is_exit_order(self, signal):
        # check if exit order exists
        if self.exit_order(signal) is not None:
            return True
        else:
            return False


def use_signal(algo_details):
    """This function is designed to be called by futures executor for multi processing of the algos
    The algo_details is the dict of details like algo, interval, security, etc of each algo.

    This function initiates the run_algo class and its methods
    It gathers the signal after processing
    It places the order if market is open."""

    global kite

    algo = algo_details['algo']
    interval = algo_details['interval']
    security = algo_details['security']
    lot_size = algo_details['lot_size']
    baseqty = algo_details['baseqty']
    days_before_expiry = algo_details['days_before_expiry']
    kite = algo_details['kite_obj']

    # Initiate class
    logger.info('Initiating processing of signals for algo {} and interval {}.\n'.format(algo, interval))
    run_algo = RunAlgo(algo, interval, security)
    logger.info('is_run_time for algo {} and interval {}: {}.\n'.format(algo, interval, run_algo.is_run_time()))

    # get signal
    if run_algo.is_run_time() or isdebug:
        signal_algo = run_algo.signal_processing()

        # for entry orders
        if run_algo.is_entry_order(signal_algo):
            new_position = {}

            signal_type = run_algo.entry_order(signal_algo)
            logger.info(
                '{} signal received for algo {} and security {}'.format(signal_text[signal_type], algo, security))

            boost_status = signal_algo['boost_status']

            # get the qty and symbol for the order
            new_position = zerodhafunctions.get_symbol(kite, signal_type, baseqty, lot_size, boost_status,
                                                       days_before_expiry)

            logger.info('based on ltp, order symbol is {} and quantity is {}'.format(new_position['tradingsymbol'],
                                                                                     new_position['quantity']))
            logger.info('Placing {} order for algo {}.\n'.format(signal_type, algo))

            # place order
            ordermanagement.trade(kite, new_position, algo, interval, signal_type)

        # for exit order
        if run_algo.is_exit_order(signal_algo):
            signal_type = run_algo.exit_order(signal_algo)

            with open('order_info.txt', 'rb') as file:
                positions = pickle.load(file)
                positions = positions[algo]
                file.close()

            entry_signal_type = 'LE' if signal_type == 'LX' else 'SE'
            positions = positions[entry_signal_type]
            order_exists_for_exit = positions['status'] == 'COMPLETE'

            if order_exists_for_exit:
                logger.info(
                    '{} signal received for algo {} and security {}'.format(signal_text[signal_type], algo, security))
                logger.info(
                    'exiting {} position of quantity {}.\n'.format(positions['tradingsymbol'], positions['quantity']))

                # place order
                ordermanagement.trade(kite, positions, algo, interval, signal_type)
