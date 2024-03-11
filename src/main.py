import json
import time

import requests
from bs4 import BeautifulSoup

from Session import Session
from exceptions.MarketPriceException import MarketPriceException
from order_types.Quote import Quote


def place_quote_to_be_executed(_quote: Quote):
    quote_ticket_uuid, challenge_id = session.create_quote_request_initialization(_quote)
    session.update_quote_request_initialization_with_tan(quote_ticket_uuid, challenge_id)

    json_quote = session.create_quote_request(_quote)

    quoteId = json_quote['quoteId']
    limit = json_quote['limit']
    quote_timestamp = json_quote['creationDateTimeStamp']

    if float(limit['value']) * 3 < 1005:
        raise RuntimeError(f'Orderbetrag unter 1000Euronen  {float(limit["value"]) * 3}')
    challenge_id = session.validate_quote_order(_quote, quoteId, quote_ticket_uuid, limit, quote_timestamp)

    return session.activate_quote_order(_quote, quoteId, quote_ticket_uuid, limit, quote_timestamp, challenge_id)


def write_order_to_file(_order):
    with open('trades.json', 'r') as _file:
        _trades = json.load(_file)
        _trades.append(_order)
    with open('trades.json', 'w') as _file:
        json.dump(_trades, _file, ensure_ascii=False, indent=4)


def check_quote_execution(_order_id):
    executed = False
    while not executed:
        orders = session.get_existing_orders().json()
        for order in orders['values']:
            if order['orderId'] == _order_id:
                if order['orderStatus'] == 'EXECUTED':
                    print(order['orderStatus'])
                    executed = True
                    write_order_to_file(order)
                elif order['orderStatus'] == 'EXPIRED':
                    print(order['orderStatus'])
                    return False
                break
    return executed


def quote_execution_manager(_quote: Quote):
    successful_execution = False
    while not successful_execution:
        try:
            open_order_quote = place_quote_to_be_executed(_quote)
        except MarketPriceException:
            print("Kein Handelskurs ermittelbar, retrying...")
            time.sleep(1)
            continue

        _order_id = open_order_quote['orderId']
        print(
            f"{open_order_quote['side']} {open_order_quote['quantity']} {open_order_quote['limit']} {open_order_quote['expectedValue']}")
        successful_execution = check_quote_execution(_order_id)


def fetch_spread(_isin):
    response = requests.get(f"https://www.comdirect.de/inf/zertifikate/{_isin}")
    soup = BeautifulSoup(response.text, 'html.parser')

    sell_text = soup.find("span", {
        "class": "realtime-indicator--value text-size--xxlarge text-weight--medium inner-spacing--xxsmall-right"}).text
    buy_text = soup.find("span", {"class": "realtime-indicator--value text-size--xxlarge text-weight--medium"}).text

    if sell_text == "--" or buy_text == "--":
        raise MarketPriceException("Kein Handelskurs (bei ComD) ermittelbar, retrying...")
    sell_price = float(sell_text.replace(",", "."))
    buy_price = float(buy_text.replace(",", "."))

    return round(sell_price - buy_price, 2)


if __name__ == "__main__":
    wkn = 'ME2USZ'  # Wkn des Produkts
    isin = "DE000ME2USZ2"  # Isin des Produkts
    accepted_spread = 0.01  # Spread bei dem ihr kaufen wollt
    quantity = 3  # Ordervolumen muss größer 1005 sein, sonnst Execption

    session = Session('properties.yml', 'access.yml')

    running = True
    while running:
        session.refresh_session_tan()
        try:
            spread = fetch_spread(isin)
        except MarketPriceException as e:
            print(e)
            time.sleep(2)
            continue

        if spread < -accepted_spread:
            print("Spread to high")
            time.sleep(2)
            continue

        # ---------------------------- Open Pos mit veneu_id der Börse Stuttgart
        buy_quote = Quote(session.depot_id, "BUY", wkn, quantity, "FA5644CBF2914EB792FEE82433789013")
        quote_execution_manager(buy_quote)
        # ------------------------------------------------------- close Pos

        sell_quote = Quote(session.depot_id, "SELL", wkn, quantity, "FA5644CBF2914EB792FEE82433789013")
        quote_execution_manager(sell_quote)

        with open('trades.json', 'r') as file:
            trades = json.load(file)
            print(f'Trades: {(len(trades)) / 2}')
            trade0 = float(trades[-2]['executions'][0]["executionPrice"]['value'])
            trade1 = float(trades[-1]['executions'][0]["executionPrice"]['value'])
            print(f'Spread payed: {round((trade0 - trade1) * 3, 2)}')

        # Einkommentieren, wenn ihr nach jedem Trade bestätigen wollt
        # key = input("press enter to continue or q to quit")
        # running = key != 'q'
