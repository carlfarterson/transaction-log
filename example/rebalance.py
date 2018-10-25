import os
import sys
import time
import ccxt
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from py.setup import Transactions, Base
from py.functions import coin_price, determine_ticker
from py.update import Update


def main():

	exchange = ccxt.binance({'options': {'adjustForTimeDifference': True})

	# BTC, ETH, XRP, BCH, LTC coins to start
	coins = ['BTC','ETH','XRP','BCH','LTC']

	# Connect to our SQL database
	db = 'transactions.db'
	engine = create_engine('sqlite:////Users/Carter/Documents/Administrative/' + db)
	Base.metadata.bind = engine
	DBSession = sessionmaker(bind=engine)
	session = DBSession()

	query = ''' SELECT * FROM transactions'''
	transactions = pd.read_sql(sql=query, con=engine)

	rebalance_num = transactions['rebalance_num'].max() + 1


	n = 1/(len(coins))
	thresh = .02
	i = 0

	while True:
		exchange = ccxt.binance({
			'options': {'adjustForTimeDifference': True},
			'apiKey': apiKey,
			'secret': secret})
		# NOTE: I had to re-create the coins list since our balance will change after
		# a transaction, and a second trade would be based on the old balance.
		# I should be able to fix this redunancy too.
		balance = exchange.fetchBalance()
		coins = [asset['asset']
				 for asset in balance['info']['balances']
				 if float(asset['free']) > 0.01 and asset['asset'] != 'GAS']

		quantities, dollar_values = [], []
		for coin in coins:
			quantity = balance[coin]['total']
			quantities.append(quantity)
			dollar_values.append(quantity * coin_price(exchange, coin))

		# Line comprehension of above loop - should I use this instead and make another
		# line comprehension for quantities? Or is it better visually to keep the current method?
		# dollar_values = np.array([balance[coin]['total'] * coin_price(coin) for coin in coins])

		# Convert our lists to np arrays since our lists don't work well with mathematical operations
		quantities = np.array(quantities)
		dollar_values = np.array(dollar_values)

		if (dollar_values.max() - dollar_values.min()) / dollar_values.sum() < 2 * n * thresh:
			break

		# To prevent infinite looping, let's break after 5 trades, but ONLY when the
		# program still is above 2 * n * thresh.
		i += 1
		if i == 5:
			sys.exit('5 trades completed. Ending rebalance.')


		# Determine if there's a trade ratio between the coins, or if we need to convert to BTC first
		tickers = determine_ticker(exchange, coins[dollar_values.argmin()], coins[dollar_values.argmax()])

		# Reference so that BTC won't be documented in the dual trade.
		if len(tickers) > 2:
			dual_trade = True
		else:
			dual_trade = False

		weight_to_move = min([dollar_values.max()/dollar_values.sum() - n, n - dollar_values.min()/dollar_values.sum()])
		trade_dollars = weight_to_move * dollar_values.sum()

		for x in range(0,len(tickers),2):
			ratio = tickers[x]
			trade_coins = ratio.split('/')

			side = tickers[x+1]
			if side == 'sell':
				trade_sides = ['sell', 'buy']
			else:
				trade_sides = ['buy', 'sell']

			# Easier way to reference both coins in our dollar_values list at the same time
			indices = [coins.index(trade_coins[0]), coins.index(trade_coins[1])]
			trade_quantities = trade_dollars / (dollar_values[indices] / quantities[indices])

			# Make trade with quantity of numerator
			exchange.create_order(ratio, 'market', side, trade_quantities[0])

			# Update SQL database
			transactions = Update(dual_trade, trade_coins, trade_sides, trade_quantities, transactions, session)

	print('Rebalance complete.')
	print('# of trades executed: ', i)
	# Print trades that are executed
	if i > 0:
		print(transactions.loc[transactions['trade_num'] > max(transactions['trade_num'] - 1)])

if __name__ == '__main__':
	main()
	time.sleep(10)
