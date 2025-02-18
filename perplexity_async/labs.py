import ssl
import json
import socket
import random
import asyncio
from threading import Thread
from curl_cffi import requests
from websocket import WebSocketApp


class AsyncMixin:
    def __init__(self, *args, **kwargs):
        self.__storedargs = args, kwargs
        self.async_initialized = False
        
    async def __ainit__(self, *args, **kwargs):
        pass
    
    async def __initobj(self):
        assert not self.async_initialized
        self.async_initialized = True
        # pass the parameters to __ainit__ that passed to __init__
        await self.__ainit__(*self.__storedargs[0], **self.__storedargs[1])
        return self
    
    def __await__(self):
        return self.__initobj().__await__()

class LabsClient(AsyncMixin):
    '''
    A client for interacting with the Perplexity AI Labs API.
    '''
    async def __ainit__(self, headers, cookies):
        self.session = requests.AsyncSession(headers=headers, cookies=cookies)
        self.timestamp = format(random.getrandbits(32), '08x')
        self.sid = json.loads((await self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.timestamp}')).text[1:])['sid']
        self.last_answer = None
        self.history = []
        
        assert (await self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.timestamp}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}')).text == 'OK'
        
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
            await asyncio.sleep(0.01)
    
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
    
    async def ask(self, query, model='sonar-pro', stream=False):
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
        
        async def stream_response(self):
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
                
                await asyncio.sleep(0.01)
        
        while True:
            if self.last_answer and stream:
                return stream_response(self)
            
            elif self.last_answer and self.last_answer['final']:
                answer = self.last_answer
                self.last_answer = None
                self.history.append({'role': 'assistant', 'content': answer['output'], 'priority': 0})
                
                return answer
            
            await asyncio.sleep(0.01)