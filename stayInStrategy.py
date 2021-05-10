import json
import os
import time
from datetime import datetime
from pytz import timezone
import colorama
from KrakenWSClient import krakenWsClient
from functions import one_ticker, ticker_work, balance_to_float, balance_alt_name, log_to_file

state = {}

import python3krakenex.krakenex.api as kapi_m
import pprint
import stayInStrategyConfig as c

k = kapi_m.API()
k.load_key(c.key_file)
ws_token = k.query_private("GetWebSocketsToken")
if ws_token.get("error"):
    raise ValueError(ws_token.get("error"))
client = krakenWsClient(
    ws_token.get("result").get("token"))
pp = pprint.pprint


def no_err_query_public(*args, **kwargs):
    result = kapi_m.API.query_public(*args, **kwargs)
    if result.get("error"):
        raise ValueError(str(result.get("error")))
    return result


def no_err_query_private(*args, **kwargs):
    result = kapi_m.API.query_private(*args, **kwargs)
    if result.get("error"):
        pass
        # raise ValueError(str(result.get("error")))
    return result


def save_state():
    # print("Saving state")
    json.dump(state, open(c.save_state_file, "w"), indent=4)


def load_state():
    global state
    if os.path.exists(c.save_state_file):
        state = json.load(open(c.save_state_file, "r"))
        print("Loaded state")


def refresh_assetpairs():
    print("Refreshing asset pairs and assets")
    c.asset_pairs = k.query_public("AssetPairs").get("result")
    c.assets = k.query_public("Assets").get("result")
    c.assets_nice = {val.get("altname"): val for val in c.assets.values()}
    return c.asset_pairs


def tradable_assetpairs(source_crypto, dest_cryptos=None):
    tradable_with = {
        key: val for key, val in c.asset_pairs.items()
        if source_crypto in val.get("wsname", "")
           and val.get("wsname").replace(source_crypto, "").replace("/", "") in (dest_cryptos or c.cryptos_to_trade)
    }
    return tradable_with


def warm_up():
    print("Warming up")
    log_to_file("Program started", "sistlog")
    load_state()
    save_state()
    refresh_assetpairs()
    state.setdefault("current_investment", {})
    state.setdefault("best_balance", {})
    register_cryptos()
    client.watch({
        "event": "subscribe",
        "subscription": {"name": "ownTrades"}
    }, on_trade, private=True)
    if state.get("current_investment", {}).get("order"):
        open_all_tickers(state.get("crypto_owned"))
    else:
        # Buy for warmup
        buy_crypto_with_eur(c.get_in_crypto, c.get_in_value)
        pass
    save_state()


orders_to_watch = []


def register_cryptos(erase=False):
    state.setdefault("buy_capability", {})
    state["greed_boxes"]={}
    greed_boxes = state.get("greed_boxes")
    buy_capability = state.get("buy_capability")
    for pair in tradable_assetpairs(state.get("crypto_owned")).values():
        greed_boxes[pair.get("wsname")] = {
            "max_seen": 1,
            "last_seen": 1,
            "detached": False
        }
        buy_capability_update_func = buy_capability.__setitem__ if erase else buy_capability.setdefault
        buy_capability_update_func(pair.get("wsname"), {
            "abandon_period": 0,
            "last": 0,
            "at_most": 0,
            "at_min": 0,
            "abandon_period_time": 0,
        })


def get_time():
    return datetime.utcnow().timestamp()


def wname_to_crypto(wsname, source_crypto=None):
    return wsname.replace(source_crypto or state.get("crypto_owned"), "").replace("/", "")


def get_comparator_value_abandon_period(buy_capability, crypto_name, greed_box, utc_time, ticker):
    if buy_capability["abandon_period"] == 0:
        buy_capability["abandon_period"] = buy_capability["last"]
    if (utc_time - buy_capability[
        "abandon_period_time"] > c.secs_for_desesperate) \
            and not state.get("disable_abandon"):
        buy_capability["abandon_period"] = buy_capability["last"]
        buy_capability["abandon_period_time"] = utc_time
        state.get("best_balance")[crypto_name] = 0
    return buy_capability["abandon_period"]


def calc_can_buy(ticker):
    owned_volume = state.get("crypto_owned_volume")
    owned_name = state.get("crypto_owned")
    can_buy = owned_volume * ticker["price"] \
        if ticker.get("name").startswith(owned_name) \
        else owned_volume / ticker["price"]
    return can_buy


def ppprint_subset(subset, legend="", elem=None, more="", orcond=[True]):
    orcond = [orcond for orc in orcond if orc]
    if not len(orcond):
        return
    elem = elem or state
    print(legend, ":", more)
    pp({
        key: val for key, val in elem.items() if key in subset
    })


def eur_price_ticker_update(ticker_raw):
    # print("Received ticker", ticker_raw[-1])
    ticker = ticker_work(ticker_raw[-1], ticker_raw[1])
    if not state.get("eur_price_at_buy"):
        state["eur_price_at_buy"] = ticker["price"]
    state["eur_price_last"] = ticker["price"]
    state["disable_abandon"] = 1 - state["eur_price_last"] / state["eur_price_at_buy"] > c.PL_DP
    state["disable_jumps"] = 1 - state["eur_price_last"] / state["eur_price_at_buy"] > c.PL_DA
    ppprint_subset(["disable_abandon", "disable_jumps", "eur_price_last", "eur_price_at_buy"], "Eur price status",
                   more=state["eur_price_last"] / state["eur_price_at_buy"],
                   orcond=[state.get("disable_jumps"), state.get("disable_abandon")])


def update_pair_statuses(ticker):
    # print("Update pair statuses for", ticker.get("name"))
    utc_time = get_time()
    crypto_name = wname_to_crypto(ticker.get("name"))
    buy_capability = state.get("buy_capability").get(ticker.get("name"))
    greed_box = state.get("greed_boxes").get(ticker.get("name"))
    can_buy = calc_can_buy(ticker)
    best_bal = state.get("best_balance").get(crypto_name, 0)
    buy_capability["last"] = ticker.get("price")
    comp_value = get_comparator_value_abandon_period(buy_capability, crypto_name, greed_box, utc_time, ticker)
    greed_box["last_seen"] = ticker.get("price") / comp_value
    # It is a bad price for me if i'm owning the other side, so we need to invert the greedbox in this case
    if ticker.get("name").endswith(state.get("crypto_owned")):
        greed_box["last_seen"] = 2 - greed_box["last_seen"]
    # print(greed_box)
    if greed_box["last_seen"] < c.jump_percentage:
        greed_box["max_seen"] = 1

    if greed_box["last_seen"] > c.jump_percentage:
        print(ticker.get("name"), "is greeding at", greed_box["last_seen"], "wich  is  above", c.jump_percentage)
    display_precision = 3

    greed_box["max_seen"] = max(greed_box["last_seen"], greed_box["max_seen"])
    greed_box["detached"] = greed_box["max_seen"] - greed_box["last_seen"] > c.greed_box_size
    crypto_display_decimals = c.assets_nice[crypto_name].get("display_decimals")
    crypto_owned_display_decimals = c.assets_nice[state.get("crypto_owned")].get("display_decimals")
    # print(f"{ticker['price']:.10f}", f"{comp_value:.10f}", f"{ticker['price']:.10f}" > f"{comp_value:.10f}",
    #      ticker["name"])
    # print("Evol:", f"{ticker['price'] / comp_value:.10f}")
    # Rounded values for display
    best_bal_r = round(best_bal, crypto_display_decimals)
    can_buy_r = round(can_buy, crypto_display_decimals)
    ratio_r = round(abs(greed_box["last_seen"] - 1) * 100, display_precision - 2)
    more_less = (colorama.Fore.GREEN + "more" if greed_box[
                                                     "last_seen"] >= 1 else colorama.Fore.LIGHTRED_EX + "less") + colorama.Fore.RESET
    more_less_best_bal = (
                             colorama.Fore.GREEN + "more" if can_buy_r > best_bal_r else colorama.Fore.LIGHTRED_EX + "less") + colorama.Fore.RESET

    more_less_best_bal = f" and {more_less_best_bal} than previously owned {best_bal_r} {crypto_name}" \
        if can_buy_r < best_bal else ""
    # previous_can_buy_r = round(can_buy_r / greed_box["last_seen"], crypto_display_decimals)
    previous_can_buy_r = round(calc_can_buy({**ticker, **{'price': buy_capability['abandon_period']}}),
                               crypto_display_decimals)
    owned_volume_r = round(state.get("crypto_owned_volume"), crypto_owned_display_decimals)
    best_greedbox_r = round(get_best_greed_box("max_seen"), display_precision)
    best_ratio_r = round(get_best_greed_box(), display_precision)
    special_comment = f'<-- Here : {ticker["price"]} {ticker["name"]}' if get_best_greed_box() == greed_box[
        'last_seen'] else ''
    ###

    print(f""" {timezone("Europe/Paris").localize(datetime.now()).strftime("%Y-%m-%d %H:%M:%S")} - {ticker.get("name")} -
    Could now get {can_buy_r} {crypto_name} wich is {ratio_r}% {more_less} than observed {previous_can_buy_r} {crypto_name}
    with owned {owned_volume_r} {state.get("crypto_owned")}{more_less_best_bal}
    \t| max greed seen is {best_greedbox_r} on {get_best_greed_box_name("max_seen")}
    \t| best ratio is {best_ratio_r} on {get_best_greed_box_name()} 
    {special_comment}
          """.replace("\n", "").replace("    ", " ").strip())
    pass


def buy_crypto_with_crypto(ticker):
    print("admit a jump")
    owned_volume = state.get("crypto_owned_volume")
    owned_name = state.get("crypto_owned")
    buy_or_sell = "sell" if ticker.get("name").startswith(owned_name) else "buy"

    # A Gauche la crypto à recevoir ou à dépenser -> volume nécéssaire pour le market
    # buy = recevoir
    # sell = separer

    # il faut donc trovuer le volume de la crypto de gauche
    # si c'est la owned, on l'a dans owned_volume
    # sinon c'est le volume*le prix

    volume_trade = owned_volume if buy_or_sell == "sell" else owned_volume / ticker["price"]

    volume_trade = volume_trade * (1 - c.curent_fee)

    asset_pair = [val for key, val in c.asset_pairs.items() if
                  ticker.get("name") == val.get("wsname", "")][0]

    volume_obtained = owned_volume / ticker["price"] if buy_or_sell == "buy" else owned_volume * ticker["price"]

    print("Trade volume:", volume_trade, buy_or_sell, ticker.get("name"))
    print("Obtained volume:", volume_obtained, buy_or_sell, ticker.get("name"))

    volume_trade = round(volume_trade, asset_pair.get("pair_decimals"))
    order_details = {
        "event": "addOrder",
        "ordertype": "market",
        "oflags": "fcib",
        "pair": ticker.get("name"),
        "type": buy_or_sell,
        "volume": str(volume_trade)
    }

    state["current_investment"]["order_tmp"] = order_details
    jumping_to_crypto = wname_to_crypto(ticker.get("name"), owned_name)
    state["current_investment"]["look_for_order"] = {
        "name": jumping_to_crypto,
        "volume_got": volume_obtained,
    }
    client.watch(order_details, on_added_order, private=True)
    print(order_details)

    log_to_file(f'Order {buy_or_sell} : {buy_or_sell} {volume_trade} {ticker.get("name").split("/")[0]}', "sistlog")
    log_to_file(f'To obtain : {volume_obtained} {jumping_to_crypto}', "sistlog")


one_jump = False


def get_best_greed_box(key="last_seen"):
    return max([x.get(key)
                for x in state.get("greed_boxes").values()])


def get_best_greed_box_name(akey="last_seen"):
    return [key for key, val in state.get("greed_boxes").items() if val.get(akey) == get_best_greed_box(akey)][0]


def ignore_or_jump(ticker):
    # print("Ignore or jump")
    global one_jump
    one_jump = os.path.exists("jump")
    can_buy = calc_can_buy(ticker)
    best_balance = state.get("best_balance").get(wname_to_crypto(ticker.get("name")), 0)
    greed_box = state.get("greed_boxes").get(ticker.get("name"))
    if (one_jump or greed_box.get("detached")) \
            and greed_box.get("last_seen") == get_best_greed_box() > 1.01 \
            and (can_buy > best_balance * c.ratio_of_best_balance_needed_to_jump) \
            and not state.get("disable_jumps"):

        # Best greed here has detached
        # do jump

        if os.path.exists("jump"):
            os.remove("jump")
        one_jump = False
        close_all_tickers()
        buy_crypto_with_crypto(ticker)
        pass
    pass


def on_ticker(ticker_raw):
    # print("Received ticker", ticker_raw[-1])
    ticker = ticker_work(ticker_raw[-1], ticker_raw[1])

    update_pair_statuses(ticker)

    ignore_or_jump(ticker)


def buy_crypto_with_eur(crypto_name, eur_value):
    asset_pair = {key: val for key, val in c.asset_pairs.items() if
                  "EUR" in val.get("wsname", "") and crypto_name in val.get("wsname", "")}

    ticker_raw = no_err_query_public(k, "Ticker", {"pair": list(asset_pair.keys())[0]})
    ticker = one_ticker(ticker_raw)
    precision = list(asset_pair.values())[0].get("pair_decimals")
    volume = round(eur_value / ticker["price"], precision)
    keypair = list(asset_pair.values())[0].get("wsname")
    print("Buying ", volume, crypto_name, "@", ticker["price"], "for a total of", eur_value, "€")

    order_details = {
        "event": "addOrder",
        "ordertype": "market",
        "pair": keypair,
        "type": "buy",
        "volume": str(volume)
    }
    client.watch(order_details, on_message=on_added_order, private=True)

    state["current_investment"]["order_tmp"] = order_details

    state["current_investment"]["look_for_order"] = {
        "volume_got": volume,
        "name": crypto_name,
    }

    log_to_file(f'Order : buy {volume} {crypto_name} @ {ticker["price"]} €  (market price)', "sistlog")


def close_all_tickers():
    global registered_ticker_websocket
    for socket in registered_ticker_websocket:
        socket.close()
    registered_ticker_websocket = []


registered_ticker_websocket = []


def register_ticker_websocket(ws):
    print("Registered a new ticker websocket", ws)
    registered_ticker_websocket.append(ws)


def open_all_tickers(crypto_name):
    print("Opening tickers for", crypto_name)
    asset_pairs_watch = [v.get("wsname") for v in tradable_assetpairs(crypto_name).values()]
    state["watched_pairs"] = asset_pairs_watch
    client.watch({
        "event": "subscribe",
        "pair": asset_pairs_watch,
        "subscription": {"name": "ticker"}
    }, on_ticker, open_callback=register_ticker_websocket)

    client.watch({
        "event": "subscribe",
        "pair": [f"{crypto_name}/EUR"],
        "subscription": {"name": "ticker"}
    }, eur_price_ticker_update, open_callback=register_ticker_websocket)


def on_trade(message):
    print("Had a trade, processing it")
    balance_r = no_err_query_private(k, "Balance").get("result")
    balance = balance_to_float(balance_r)
    # Update balances
    balance_nice = balance_alt_name(balance, c.assets)
    state["balance"] = balance_nice
    shown_kraken = round(state["crypto_owned_volume"], c.assets_nice[state.get("crypto_owned")]["display_decimals"])
    # Owned_crypto_volume = min(bal,owned_vol)
    print("OWNED AFAIK", state.get("crypto_owned_volume"))
    print("OWNED KRAKEN", balance_nice.get(state.get("crypto_owned")))

    print("AS SHOWN ON KRAKEN UI", shown_kraken)
    if abs(1 - state.get("crypto_owned_volume") / balance_nice.get(state.get("crypto_owned"))) < 0.001:
        state["crypto_owned_volume"] = balance_nice.get(state.get("crypto_owned"))
    state["crypto_owned_volume"] = min(state.get("crypto_owned_volume"),
                                       balance_nice.get(state.get("crypto_owned")))
    state.get("best_balance").update({
        state.get("crypto_owned"): max(state.get("best_balance").get("crypto_owned", 0),
                                       state.get("crypto_owned_volume"))

    })
    print("Owned volume of", state.get("crypto_owned"), " is ", state.get("crypto_owned_volume"))
    log_to_file(f'Owning volume of {state.get("crypto_owned_volume")} {state.get("crypto_owned")}', "sistlog")


def on_added_order(message):
    # 3 cases :
    # Stop tickers
    # - Order is not from the script :
    # Ignore and reopen tickers, continue greed
    # - Order  has error
    # Ignore and reopen tickers, continue greed
    # - Order is from the script
    #   Update owned volume from order done
    #   Update owned crypto from order done
    # Open tickers

    close_all_tickers()
    order_tmp = state.get("current_investment", {}).get("order_tmp", {})
    look_for_order = state.get("current_investment", {}).get("look_for_order", {})

    print("Volume", order_tmp.get("volume"))
    print("Type", order_tmp.get("type"))
    print("OType", order_tmp.get("ordertype"))
    print("Crypto name", look_for_order.get("name"))

    if (
            order_tmp.get("volume") in message.get("descr", "")
            and order_tmp.get("type") in message.get("descr", "")
            and order_tmp.get("ordertype") in message.get("descr", "")
            and look_for_order.get("name") in message.get("descr", "")

    ):
        print("this is my order @ market with no errors !", message)
        state["current_investment"]["order"] = message
        state["crypto_owned"] = look_for_order.get("name")
        state["crypto_owned_volume"] = look_for_order.get("volume_got")
        state["eur_price_at_buy"] = 0
        register_cryptos()
        save_state()

    open_all_tickers(state.get("crypto_owned"))
    logmessage = f'Received added order {message.get("descr", message.get("errorMessage", "no err, no desc"))}'
    print(logmessage)
    log_to_file(logmessage, "sistlog")


warm_up()

while True:
    save_state()
    time.sleep(5)
