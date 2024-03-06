import json
from datetime import datetime

with open('trades.json', 'r') as file:
    orders = json.load(file)

buys = []
sells = []

for order in orders:
    if order['side'] == "BUY":
        buys.append(order)
    if order['side'] == "SELL":
        sells.append(order)

trades = [{"buy": buys[i], "sell": sells[i]} for i in range(min(len(buys), len(sells)))]

for trade in trades:
    buy_price = float(trade['buy']['executions'][0]["executionPrice"]['value'])
    sell_price = float(trade['sell']['executions'][0]["executionPrice"]['value'])
    trade['spread'] = (round((sell_price - buy_price) * 3, 2))
    if "executionTimestamp" in trade['buy']['executions'][0]:
        buy_timestamp = datetime.strptime(trade['buy']['executions'][0]['executionTimestamp'][:-10], "%Y-%m-%dT%H:%M:%S")
        sell_timestamp = datetime.strptime(trade['sell']['executions'][0]['executionTimestamp'][:-10], "%Y-%m-%dT%H:%M:%S")
        trade['trade_duration'] = (sell_timestamp - buy_timestamp).total_seconds()
    else:
        trade['trade_duration'] = "unknown"

for trade in trades:
    print(f'Spread: {trade["spread"]} - duration: {trade["trade_duration"]} seconds')


sum = 0
for trade in trades:
    sum += trade['spread']

print(f'Profit: {sum + len(trades)} EURO mit {len(trades)} Trades')
