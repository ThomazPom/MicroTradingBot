# Import WebSocket client library (and others)
import json

import websocket
import _thread
import time

class krakenWsClient:
    api_domain_public = "wss://ws.kraken.com/"
    api_domain_private = "wss://ws-auth.kraken.com/"
    heartbeat_str = '{"event":"heartbeat"}'

    def __init__(self, private_token):
        self.private_token = private_token
        self.watch({"event": "subscribe", "subscription": {"name": "ownTrades"}}, private=True)

    def ws_open(self, ws, payload):
        ws.send(json.dumps(payload))
        print(payload, ws.url)
        pass

    def ws_thread(self, payload, onmessage, private, close):

        def my_print(*args):
            response = json.loads(args[1])
            if not (type(response) is dict and response.get("event", {}) in ["heartbeat","subscriptionStatus","systemStatus"]):
                onmessage(response)
            if close:
                args[0].close()

        ws = websocket.WebSocketApp(self.api_domain_private if private else self.api_domain_public,
                                    on_open=lambda ws: self.ws_open(ws, payload),
                                    on_message=my_print)

        ws.run_forever()

    def watch(self, payload, on_message=lambda x: None, private=False, close=False):
        if private:
            if payload.get("subscription"):
                payload["subscription"]["token"] = self.private_token
            else:
                payload["token"] = self.private_token
        _thread.start_new_thread(self.ws_thread, (payload, on_message, private, close))
        pass
