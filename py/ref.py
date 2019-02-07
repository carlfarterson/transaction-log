class Portfolio(object):
	'''
	Represents our account balance on Binance
	coins	- list of coin names we are invested in
	units	- list of the units for each coin held
	prices 	- list of the most recent dollar price for each coin held
	d_vals  - list of the dollar values for each coin held (units * prices)
	'''
	def __init__(self):
		binance = exchange.connect()
		balance = binance.fetchBalance()
		coins =	[asset['asset']
				 for asset in balance['info']['balances']
				 if (float(asset['free']) > 0.01)
				 and (asset['asset'] != 'GAS')
				 and (asset['asset'] != 'BAT')]

		units = np.array([balance[coin]['total'] for coin in coins])
		prices = [exchange.fetch_price(coin) for coin in coins]
		self.coins = coins
		self.units = units
		self.prices = prices
		self.d_vals = units * prices


# ------------------------------------------------------------------------------
# TODO: add column into simulations CSV for coin price at time of trade
class SimPortfolio(object):
	def __init__(self, coins):
		self.coins = coins
		self.units = [1000 / histPrices[coin][0] for coin in coins]
# ------------------------------------------------------------------------------
# Testing w/ using Portfolio in a JSON-like structure
class TestNewPortfolio(object):
	binance = exchange.connect()
	balance = binance.fetchBalance()
	def __init__(self):
		# TODO: convert code before to map() for practice
		coins = [asset['asset']
				 for asset in balance['info']['balances']
				 if (float(asset['free']) > 0.01) and (asset['asset'] != 'GAS')]
		# TODO: can the for loop be replicated with map() ?
		for coin in coins:
			units = float(balance[coin]['free'])
			currentPrice = exchange.fetch_price(coin)
			setattr(self, coin, {
				'units': units,
				'currentPrice': currentPrice,
				'dollarValue': units * currentPrice
			})
# ------------------------------------------------------------------------------