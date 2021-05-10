import json
from datetime import datetime

from pytz import timezone


def obj_to_json(o):
    return json.dumps(o)


def array_to_foats(arr):
    return [float(val) for val in arr]


def ticker_to_float(ticker):
    for key, val in ticker.items():
        if type(val) is list:
            ticker[key] = array_to_foats(val)


def ticker_work(key, val):
    ticker_to_float(val)
    val["name"] = key
    val["price"] = (val.get("a")[0] + val.get("b")[0]) / 2
    val["low"] = val.get("l")[1]
    val["high"] = val.get("h")[1]
    return val


def tickers_treat(tickers):
    return [ticker_work(key, val) for key, val in tickers.get("result")]


def balance_to_float(balance):
    return {key: float(val) for key, val in balance.items()}


def one_ticker(tickers):
    return ticker_work(list(tickers.get("result").keys())[0], list(tickers.get("result").values())[0])


def balance_alt_name(balance, assets):
    return {assets.get(key).get("altname"): val for key, val in balance.items() if assets.get(key)}



def log_to_file(log, logtype="log"):
    # Open a file with access mode 'a'
    if not type(log) is list:
        log = [log]
    file_object = open(f'{logtype}.log', 'a')
    timestr = timezone("Europe/Paris").localize(datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    for l in log:
        file_object.write(f"{timestr}\t {l}\n")
    file_object.close()



