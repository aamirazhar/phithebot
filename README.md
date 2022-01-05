# phithebot
This repository contains codes of automated trade execution system for Indian stock market using zerodha APIs.

## Introduction
This bot is an automated trade execution system build for Indian markets. It works with Zerodha account and is built using their APIs. The system is designed to be scalable in terms of strategies it can deploy. It can be deployed on cloud based computing engines and scheduled to kick-off before markets starts. The system is capable of self login. Subscription to Zerodha APIs (including their historical data api) is required.

The system in its current form is designed to trade at the money options. Limit orders with price near last traded price are place. Futures trading is also possible with minor modifications in the code.

## Configuration and supporting files
1. **zerodha_credentials.txt**: This file contains the credentials of user's zerodha account. The details are used in module zerodhalogin_chrome.py to log in the user automatically.
2. **request_token.txt**: This file is used to store the request token generated during the login process. This file is set to "first login".
3. **access_token.txt**: This file is used to store the access token generated during the login process. This file is set to "first login". If this file contains any other charecters, then the contents are assumed to be access token and is used in login process.
4. **algo_list.txt**: This file is configuration of all strategies deployed for execution. The details of the configuration are:
    - algo: the name of the strategy. This name is used as identifier in various modules.
    - interval: the frequency at which the strategy runs. This is same as the candle interval on a chart. Values (minute, 15minute, 60minute, etc) are as per zerodha definition of interval.
    - security: The ticker of security (as per zerodha) for which the strategy is deployed.
    - lot_size: the size of one lot of the security's options (or futures).
    - baseqty: number of lots which are executed when signal is generated.
    - days_before_expiry: the options of next month are executed when remaining days in option expiry of current month < days_before_expiry.
5. **order_info**: This file stores information of current orders placed by the system. This file is used to monitor trades (when they are still open) and to check whether a trade was executed if an exit signal is received. When no trade was executed as per this file, the exit signal is ignored.
6. **instruments.csv**: This file is downloaded from https://api.kite.trade/instruments and contains the list of instruments being traded on the exchange. This file is used to chose the instrument/ticker ID of relevant options.
7. **requirements.txt**: Project requirements. In case other specific packages are used in strategy modules, they need to be installed by the user. One common package needed in the strategy module is 'talib'.


## Modules
1. **main_chrome.py**: This is the main module which calls other modules/functions.
2. **zerodhalogin_chome.py**: This module is called from main_chrome.py and handles the login process into zerodha account of the user. The login process requires chrome to be installed on the machine.
3. **multiprocess_function.py**: This module is called from main_chrome.py. It runs the algorithm which consists of fetching historical data at relevant time, calling the configured strategy for signal processing, sending the entry/exit orders and documenting the order details in respective txt files.
4. **ordermanagement.py**: This module contains custom functions for placing and monitoring of orders.
5. **zerodhafunctions.py**: This module contains custom functions to get historical data, current price and relevant symbol (of options for which order needs to be placed).
6. **supportfunctions.py**: This module contains custom functions to support the overall operations of the system.
7. Apart from above modules, separate modules of each strategy deployed as per algo_list.txt file is needed. The name of module should be same as name of algo defined in algo_list.txt file. See **strategy1.py** as an example.
