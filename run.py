import time
from copy import copy
from colorama import Fore
import math
import websocket
import functools
import config as c
import functions as f
import python3krakenex.krakenex.api as kapi_m
import pprint

from KrakenWSClient import krakenWsClient

pp = pprint.pprint
k = kapi_m.API()
k.load_key(c.key_file)
c.ws_token = k.query_private("GetWebSocketsToken").get("result").get("token")
c.precision = k.query_public("AssetPairs", dict(pair=c.assetpair_no_slash)).get("result").get(c.assetpair_no_slash).get(
    "pair_decimals")
ticker_history = []
ready = False

openOrders = {
    "buy": None,
    "sell": None
}


def on_open_order(orders):
    try:
        global openOrders
        tmp_open_orders = {}
        for order_raw in orders[0]:

            keys = list(order_raw.keys())
            orderid = keys[0]
            order = order_raw[orderid]
            order["orderid"] = orderid

            if order.get("descr") and order.get("descr").get("pair") == c.assetpairwatch:
                tmp_open_orders[order.get("descr").get("type")] = order
            else:
                for a_type, p_order in openOrders.items():
                    if p_order and p_order.get("orderid") == orderid:
                        tmp_open_orders[a_type] = {**p_order, **order}
        decide_order_open_change(tmp_open_orders)
        openOrders.update(tmp_open_orders)
    except Exception as rerex:
        print("Error on_open_order", str(rerex))


def on_added_order(message):
    print("Added Order ", message)


def min_price_of_tickers():
    global ticker_history
    return functools.reduce(lambda x, item: min(x, item.get("price")), ticker_history, math.inf)
    pass


def max_price_of_tickers():
    global ticker_history
    return functools.reduce(lambda x, item: max(x, item.get("price")), ticker_history, -1)
    pass


def decide_order_ticker(ticker, ts, ready):
    global openOrders

    if ready and not openOrders.get("buy") and not openOrders.get("sell") and c.enable_buys:
        try:
            price = min_price_of_tickers()

            print("Adding buy order: No open order either at sell or buy")
            client.watch({
                "event": "addOrder",
                "ordertype": "limit",
                "pair": c.assetpairwatch,
                "price": str(price),
                "type": "buy",
                "volume": str(round(c.invest / price, 6))
            }, on_added_order, private=True)
            openOrders["buy"] = {"ws_pending": 1}
        except Exception as rerex:
            print("ERROR", c.assetpairwatch, c.invest / price)
    elif False:
        print("Not buying :")
        print("Ready", ready)
        print("Buy", openOrders.get("buy"))
        print("Sell", openOrders.get("sell"))
    pass


def decide_order_open_change(tmp_openOrders):
    global openOrders
    try:
        maxprice = max_price_of_tickers()
        bopen = openOrders.get("buy")
        bopen_tmp = tmp_openOrders.get("buy")

        sopen = openOrders.get("sell")
        sopen_tmp = tmp_openOrders.get("sell")
        # Si il y avait un achat, qu'il y est plus et que y'a pas deja de vente prévue on en ajoute une
        if not sopen \
                and (bopen and bopen_tmp  # Si on a un update d'un achat passé de open a close
                     and bopen.get("orderid") == bopen_tmp.get("orderid")
                     and bopen.get("status") == "open"
                     and bopen_tmp.get("status") in ["closed"]) \
                and c.enable_sells:
            print("Adding sell order: A buy order has been ", bopen_tmp.get("status"), "at", bopen_tmp.get("avg_price"),
                  "for a cost of", bopen_tmp.get("cost"))
            client.watch({
                "event": "addOrder",
                "ordertype": "limit",
                "pair": c.assetpairwatch,
                "price": str(
                    round(max(maxprice if c.use_maxprice else 0,
                              (float(bopen_tmp.get("cost")) + c.wanted_win) / float(bopen_tmp.get("vol")),
                              float(bopen_tmp.get("avg_price")) * c.multiplier_price_win
                              ), c.precision,
                          )
                ),
                "type": "sell",
                "volume": str(bopen.get("vol"))
            }, on_added_order, private=True)
            openOrders["sell"] = {"ws_pending": 1}

        if bopen and bopen_tmp and bopen.get("status") == "open" and bopen_tmp.get("status") in ["canceled"]:
            tmp_openOrders["buy"] = None
            print("Forgetting buy order as it is ", bopen_tmp.get("status"),
                  "BTW authorizing new orders as if there is no sell order open")

        # Si ona  un update d'une vente passée de open à close

        if sopen and sopen_tmp and sopen.get("status") == "open" and sopen_tmp.get("status") in ["closed",
                                                                                                 "canceled"]:
            tmp_openOrders["sell"] = None
            tmp_openOrders["buy"] = None
            print("Forgetting sell order as it is ", sopen_tmp.get("status"),
                  "BTW authorizing new orders as if there is no buy order open")
    except Exception as rerex:
        print(str(rerex))


def get_ticker_price(ticker):
    try:
        a = ticker.get('ticker').get("a")[0]
        b = ticker.get('ticker').get("b")[0]


    except Exception as rerex:
        print("Error on get_ticker_price", str(rerex))
    return round((float(a) + float(b)) / 2, c.precision)


def on_ticker(message):
    global ticker_history, ready
    try:
        ts = time.time()
        ticker = {"time": ts, "ticker": message[1]}
        ticker_history.append(ticker)
        ticker["price"] = get_ticker_price(ticker)
        ready_tmp = len(ticker_history) and ticker_history[0]["time"] <= ts - c.time_to_watch
        if ready_tmp != ready:
            print("Ready state changed to", ready_tmp)
        ready = ready_tmp
        ticker_history = [a_ticker for a_ticker in ticker_history if a_ticker["time"] > ts - c.time_to_watch]
        if ready:
            decide_order_ticker(ticker, ts, ready)
        else:
            ready_time = int(ticker_history[0].get("time") + c.time_to_watch - ts)
            if ready_time > 12:
                print("Ready in ", int(ticker_history[0].get("time") + c.time_to_watch - ts), "s")
        min, max = [min_price_of_tickers(), max_price_of_tickers()]
        if (min == max):
            max *= 0.1
        waitingfor = None
        waitingdetails = ""

        bopen = openOrders["buy"]
        sopen = openOrders["sell"]

        if sopen and sopen.get("vol"):
            waitingfor = "sell"
            sell_price = float(sopen.get("descr").get("price"))
            sell_vol = float(sopen.get("vol"))
            if bopen and bopen.get("cost"):
                buy_cost = float(bopen.get("cost"))
                buy_price = float(bopen.get("descr").get("price"))
                waitingdetails = f"""{sell_vol} and win {round(
                    sell_price * sell_vol - buy_cost)} @price {sell_price}, @buyprice {buy_price}"""
            else:
                waitingdetails = f'{sell_vol} and win of {round(sell_price * sell_vol - c.invest)} @price {sell_price}'
                pass
        if bopen and bopen.get("vol") and not sopen:
            waitingfor = "buy"
            buy_vol = float(bopen.get("vol"))
            buy_price = float(bopen.get("descr").get("price"))
            buy_cost = round(buy_vol * buy_price)
            waitingdetails = f"""{buy_vol} @{buy_price} for a total of {buy_cost}"""

        print("Price Range ", c.time_to_watch, "s", "min:", min, "max:", max, "price:", ticker["price"], "Ratio:",
              round((ticker["price"] - min) / (max - min) * 100), "%",
              "Waiting:", waitingfor if waitingfor else "Nothing", waitingdetails)
    except Exception as rerex:
        print("Error on_ticker : ", rerex)
        print(sopen)
        print(bopen)


client = krakenWsClient(c.ws_token)
client.watch({
    "event": "subscribe",
    "pair": [c.assetpairwatch],
    "subscription": {"name": "ticker"}
}, on_ticker)

client.watch({
    "event": "subscribe",
    "subscription": {"name": "openOrders"}
}, on_open_order, private=True)

while True:
    time.sleep(5)
