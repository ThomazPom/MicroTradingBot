# Import WebSocket client library (and others)
import json

import _thread
import time
import traceback

import websocket


class krakenWsClient:
    api_domain_public = "wss://ws.kraken.com/"
    api_domain_private = "wss://ws-auth.kraken.com/"
    heartbeat_str = '{"event":"heartbeat"}'

    def __init__(self, private_token):
        self.private_token = private_token
        self.watch({"event": "subscribe", "subscription": {"name": "ownTrades"}}, private=True)

    def ws_open(self, ws, payload, open_callback=lambda x: x):
        ws.send(json.dumps(payload))
        print(payload, ws.url)
        if open_callback:
            open_callback(ws)

    def ws_thread(self, payload, onmessage, private, close, open_callback=False):

        def my_print(*args):
            response = json.loads(args[1])
            if not (type(response) is dict and response.get("event", {}) in ["heartbeat", "subscriptionStatus",

                                                                          "systemStatus"]):
                try:
                    onmessage(response)
                except BaseException as e:
                    print('\033[91m',"ERROR IN THREAD :",str(e),'\033[0m')
                    traceback.print_exc()
            if close:
                args[0].close()

        ws = websocket.WebSocketApp(self.api_domain_private if private else self.api_domain_public,
                                    on_open=lambda ws: self.ws_open(ws, payload, open_callback),
                                    on_message=my_print)

        ws.run_forever()

    def watch(self, payload, on_message=lambda x: None, private=False, close=False, open_callback=False):
        if private:
            if payload.get("subscription"):
                payload["subscription"]["token"] = self.private_token
            else:
                payload["token"] = self.private_token
        _thread.start_new_thread(self.ws_thread, (payload, on_message, private, close, open_callback))
        pass
