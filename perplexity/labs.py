import json
import time
import random
import requests
from threading import Thread
from websocket import WebSocketApp

def case_fixer(headers):
    new_headers = {}

    for key, value in headers.items():
        new_headers.update({'-'.join([word[0].upper() + word[1:] for word in key.split('-')]): value})
    
    return new_headers

# client class for interactions with perplexity ai labs webpage
class LabsClient:
    def __init__(self, headers, cookies):
        self.session = requests.Session()
        self.session.headers.update(case_fixer(headers))
        self.session.cookies.update(cookies)

        # generate random values for session init
        self.t = format(random.getrandbits(32), '08x')
        self.sid = json.loads(self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}').text[1:])['sid']
        self._last_answer = None
        self.history = []

        assert self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}').text == 'OK'
        #self.session.get(f'https://labs-api.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}&sid={self.sid}')

        # setup websocket communication
        self.ws = WebSocketApp(
            url=f'wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket&sid={self.sid}',
            cookie='; '.join([f'{x}={y}' for x, y in self.session.cookies.get_dict().items()]),
            header={'User-Agent': self.session.headers['User-Agent']},
            on_open=lambda ws: ws.send('2probe'),
            on_message=self.on_message,
            on_error=lambda ws, err: print(f'Error: {err}'),
        )

        # start webSocket thread
        Thread(target=self.ws.run_forever).start()
        time.sleep(1)

    # message handler function for Websocket
    def on_message(self, ws, message):
        if message == '2':
            ws.send('3')
        elif message == '3probe':
            ws.send('5')

        if message.startswith('42'):
            response = json.loads(message[2:])[1]

            if 'status' in response:
                self._last_answer = response
                self.history.append({'role': 'assistant', 'content': response['output'], 'priority': 0})

    # method to ask to perplexity labs
    def ask(self, query, model='llama-3.1-sonar-large-128k-online'):
        assert model in ['llama-3.1-sonar-large-128k-online', 'llama-3.1-sonar-small-128k-online', 'llama-3.1-sonar-large-128k-chat',
                         'llama-3.1-sonar-small-128k-chat', 'llama-3.1-8b-instruct', 'llama-3.1-70b-instruct', 'Liquid LFM 40B'], 'Search modes --> ["llama-3.1-sonar-large-128k-online", "llama-3.1-sonar-small-128k-online", "llama-3.1-sonar-large-128k-chat", "llama-3.1-sonar-small-128k-chat", "llama-3.1-8b-instruct", "llama-3.1-70b-instruct", "Liquid LFM 40B"]'

        self._last_answer = None
        self.history.append({'role': 'user', 'content': query, 'priority': 0})

        self.ws.send('42' + json.dumps([
            'perplexity_labs',
            {
                'version': '2.13',
                'source': 'default',
                'model': {
                    'llama-3.1-sonar-large-128k-online': 'llama-3.1-sonar-large-128k-online',
                    'llama-3.1-sonar-small-128k-online': 'llama-3.1-sonar-small-128k-online',
                    'llama-3.1-sonar-large-128k-chat': 'llama-3.1-sonar-large-128k-chat',
                    'llama-3.1-sonar-small-128k-chat': 'llama-3.1-sonar-small-128k-chat',
                    'llama-3.1-8b-instruct': 'llama-3.1-8b-instruct',
                    'llama-3.1-70b-instruct': 'llama-3.1-70b-instruct',
                    'Liquid LFM 40B': '/models/LiquidCloud'}[model],
                'messages': self.history
            }
        ]))


        while not self._last_answer:
            pass

        return self._last_answer

    def add_custom_message(self, content, role='assistant'):
        self.history.append({'role': role, 'content': content, 'priority': 0})

    def clear_history(self):
        self.history.clear()