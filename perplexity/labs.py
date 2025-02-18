import ssl
import json
import time
import socket
import random
from threading import Thread
from curl_cffi import requests
from websocket import WebSocketApp

class LabsClient:
    '''
    A client for interacting with the Perplexity AI Labs API.
    '''
    def __init__(self, headers, cookies):
        self.session = requests.Session(headers=headers, cookies=cookies)
        self.timestamp = format(random.getrandbits(32), '08x')
        self.sid = json.loads(self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.timestamp}').text[1:])['sid']
        self.last_answer = None
        self.history = []
        
        assert self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.timestamp}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}').text == 'OK'
        
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        self.sock = context.wrap_socket(socket.create_connection(('www.perplexity.ai', 443)), server_hostname='www.perplexity.ai')
        
        self.ws = WebSocketApp(
            url=f'wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket&sid={self.sid}',
            header={'User-Agent': self.session.headers['User-Agent']},
            cookie='; '.join([f'{key}={value}' for key, value in self.session.cookies.get_dict().items()]),
            on_open=lambda ws: (ws.send('2probe'), ws.send('5')),
            on_message=self._on_message,
            on_error=lambda ws, error: print(f'Websocket Error: {error}'),
            socket=self.sock
        )
        
        Thread(target=self.ws.run_forever, daemon=True).start()
        
        while not (self.ws.sock and self.ws.sock.connected):
            time.sleep(0.01)
    
    def _on_message(self, ws, message):
        '''
        Websocket message handler
        '''
        if message == '2':
            ws.send('3')
            
        if message.startswith('42'):
            response = json.loads(message[2:])[1]
            
            if 'final' in response:
                self.last_answer = response
    
    def ask(self, query, model='sonar-pro', stream=False):
        '''
        Query function
        '''
        assert model in ['sonar-pro', 'sonar', 'sonar-reasoning-pro', 'sonar-reasoning'], 'Search models -> ["sonar-pro", "sonar", "sonar-reasoning-pro", "sonar-reasoning"]'
        
        self.last_answer = None
        self.history.append({'role': 'user', 'content': query})
        
        self.ws.send('42' + json.dumps([
            'perplexity_labs',
            {
                'messages': self.history,
                'model': model,
                'source': 'default',
                'version': '2.18',
            }
        ]))
        
        def stream_response(self):
            answer = None
            
            while True:
                if self.last_answer != answer:
                    answer = self.last_answer
                    yield answer
                
                if self.last_answer['final']:
                    answer = self.last_answer
                    self.last_answer = None
                    self.history.append({'role': 'assistant', 'content': answer['output'], 'priority': 0})
                    
                    return
                
                time.sleep(0.01)
        
        while True:
            if self.last_answer and stream:
                return stream_response(self)
            
            elif self.last_answer and self.last_answer['final']:
                answer = self.last_answer
                self.last_answer = None
                self.history.append({'role': 'assistant', 'content': answer['output'], 'priority': 0})
                
                return answer
            
            time.sleep(0.01)