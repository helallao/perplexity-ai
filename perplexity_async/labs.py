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
    async def __ainit__(self):
        self.session = requests.AsyncSession(headers={
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'max-age=0',
            'dnt': '1',
            'priority': 'u=0, i',
            'sec-ch-ua': '"Not;A=Brand";v="24", "Chromium";v="128"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-bitness': '"64"',
            'sec-ch-ua-full-version': '"128.0.6613.120"',
            'sec-ch-ua-full-version-list': '"Not;A=Brand";v="24.0.0.0", "Chromium";v="128.0.6613.120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"19.0.0"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        }, impersonate='chrome')
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
    
    async def ask(self, query, model='r1-1776', stream=False):
        '''
        Query function
        '''
        assert model in ['r1-1776', 'sonar-pro', 'sonar', 'sonar-reasoning-pro', 'sonar-reasoning'], 'Search models -> ["r1-1776", "sonar-pro", "sonar", "sonar-reasoning-pro", "sonar-reasoning"]'
        
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