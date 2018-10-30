from database import db_session, engine, init_db
from models import Transaction
from functions import coin_price
from flask import Flask, request, render_template, redirect
from oauth2client.client import flow_from_clientsecrets, FlowExchangeError
from datetime import datetime
import pandas as pd
import numpy as np
from datetime import datetime
import ccxt

# BTC, ETH, XRP, BCH, LTC coins to start
coins = ['BTC','ETH','LTC']

# Date range - use median of starting mcap / ending mcap
hist_cap = pd.read_csv('data/historical_market_cap.csv')
hist_cap = np.array(hist_cap)

start_dates = hist_cap[:len(hist_cap) - 365]
end_dates = hist_cap[365:]

cap_diffs = list(end_dates[:, 3] - start_dates[:, 3])
if len(cap_diffs) % 2 == 0:
	cap_diffs.pop(len(cap_diffs) - 1)

# Start date for simulations
start_date = 0

hist_prices = pd.read_csv('data/historical_prices.csv')
dates = hist_prices['date']
hist_prices = np.array(hist_prices[coins])

# Limit to current date range
hist_prices = hist_prices[start_date:start_date + 365]
dates = dates[start_date:start_date + 365]

fees = 0
rate = 0.0075
start_amt = 5000
thresh = 0.01
avg_weight = 1 / len(coins)
weighted_thresh = (avg_weight * thresh)

amt_each = start_amt / len(coins)
starting_prices = hist_prices[0]
coin_amts = amt_each / starting_prices

# Create our db
init_db()

# Simulate initial purchase of coins on day 0
day = datetime.fromtimestamp(dates[0])
for i in range(len(coins)):
	price = starting_prices[i]
	quantity = coin_amts[i]
	purchase = Transaction(
		date = day,
		coin = coins[i],
		side = 'buy',
		units = quantity,
		price_per_unit = price,
		fees = price * quantity * 0.0075,
		previous_units = 0,
		cumulative_units = quantity,
		transacted_value = price * quantity,
		previous_cost = 0,
		cost_of_transaction = None,
		cost_per_unit = None,
		cumulative_cost = price * quantity,
		gain_loss = 0,
		realised_pct = None
	)
	db_session.add(purchase)
	db_session.commit()


# Simulate daily rebalance for one year
for day in range(1, len(hist_prices)):
	purchase_date = datetime.fromtimestamp(dates[day])
	while True:

		# connect to db first
		transactions = pd.read_sql_table('transactions', con=engine)

		# Declaring variables
		d_vals = hist_prices[day] * coin_amts
		d_vals_total = sum(d_vals)
		l_index, h_index = d_vals.argmin(), d_vals.argmax()
		weight_diffs = [avg_weight - d_vals[l_index]/d_vals_total, d_vals[h_index]/d_vals_total - avg_weight]
		weight_to_move = min(weight_diffs)

		# If the weighted_thresh is greater than the minimum weight difference,
		# We're close enough to stop rebalancing
		if weighted_thresh > min(weight_diffs):
			break

		d_amt = weight_to_move * d_vals_total
		trade_sides = ['buy','sell']
		trade_coins = [coins[l_index], coins[h_index]]

 		# pretend we perfectly swap the coins and don't need a BTC intermediary trade
		# ASSUMPTION: trade rate will always be .0025, which means there's a perfect ratio
		# If we have to convert to BTC first, two trades will be executed, a.k.a. 0.005

		# the ratio of buy/sell will never matter
		# BECAUSE WE WILL ALWAYS BE BUYING THE (NOT LOWER WEIGHT) BUT COIN OF
		# LOWEST WEIGHT, AND SELLING THE COIN OF HEAVIEST WEIGHT
		# Sell h_index(or coin with most weight)/buy l_index(or coin with least weight)

		# Get coin quantities to buy/sell based on current market price
		l_quantity = d_amt / hist_prices[day, l_index]
		h_quantity = d_amt / hist_prices[day, h_index]
		trade_quantities = [l_quantity, h_quantity]

		# Adjust coin quantities
		coin_amts[l_index] += l_quantity
		coin_amts[h_index] -= h_quantity

		# Document trade
		for coin, side, quantity in zip(trade_coins, trade_sides, trade_quantities):

			temp = transactions.loc[transactions['coin'] == coin]
			previous_units = temp['cumulative_units'].values[len(temp)-1]
			previous_cost = temp['cumulative_cost'].values[len(temp)-1]

			if side == 'buy':
				transacted_value = d_amt * (1 + .0075)
				cumulative_cost = previous_cost + transacted_value
				cumulative_units = previous_units + quantity
				# cost_of_transaction, cost_per_unit, realised_pct are N/A
				cost_of_transaction, cost_per_unit, realised_pct = None, None, None, None
			else:
				transacted_value = d_amt * (1 - .0075)
				cost_of_transaction = quantity / previous_units * previous_cost
				cost_per_unit = previous_cost / previous_units

				cumulative_cost = previous_cost - transacted_value
				cumulative_units = previous_units - quantity
				gain_loss = transacted_value - cost_of_transaction
				realised_pct = gain_loss / cost_of_transaction

			# push to SQL
			sim_purchase = Transaction(
				date = purchase_date,
				coin = coin,
				side = side,
				units = quantity,
				price_per_unit = hist_prices[day, coins.index(coin)],
				fees = d_amt * .0075,
				previous_units = previous_units,
				cumulative_units = cumulative_units,
				transacted_value = transacted_value,
				previous_cost = previous_cost,
				cost_of_transaction = cost_of_transaction,
				cost_per_unit = cost_per_unit,
				cumulative_cost = cumulative_cost,
				gain_loss = gain_loss,
				realised_pct = realised_pct
			)

			db_session.add(sim_purchase)
			db_session.commit()

#transactions.loc[transactions['previous_cost'] < 100]
