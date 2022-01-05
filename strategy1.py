# -*- coding: utf-8 -*-
"""
Created on Sat Apr 10 02:05:31 2021

@author: aamir
"""

import talib as ta
import numpy as np


def signal(data):
    """Signal processing returns the original dataframe with three more columns containing long & short signals and boost
    status.
    The signals give long/Short values for entry, exitLong/exitShort for exit, hold to maintain position and
    NaN for no action. """

    df = data

    ######################################
    ######################################

    """Your strategy code using df data"""

    ######################################
    ######################################

    # Below three columns in df are required.
    # They are results of signal processing and are read by other modules to place orders or exit positions.
    # column 'long_Signal' can have 4 values: 'LE', 'LX', 'Hold' and 'NaN'.
    # column 'short_Signal' can have 4 values: 'SE', 'SX', 'Hold' and 'NaN'.
    # column 'boost_signal' can have 3 values: 1, -1 and 0.

    df['long_signal'] # = long_status
    df['short_signal'] # = short_status
    df['boost_status'] # = boost_status

    # LE: Long; LX: exit long
    # SE: Short; SX: exit short
    # Hold: hold the LE/SE position
    # NaN: No signal
    # Boost = 1, the long position is doubled; Boost = -1, the short position is doubled; Boost = 0, no effect.

    return df
