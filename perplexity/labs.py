# Importing necessary modules
# ssl: SSL/TLS support for secure connections
# json: JSON parsing and serialization
# time: Time-related functions for delays
# socket: Low-level networking interface
# random: Random number generation
# threading: For running background tasks
# curl_cffi: HTTP requests
# websocket: WebSocket client for real-time communication
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

    def __init__(self):
        # Initialize HTTP session with default headers
        self.session = requests.Session(headers={
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
        })

        # Generate a unique timestamp for session identification
        self.timestamp = format(random.getrandbits(32), '08x')

        # Establish a session with the Perplexity Labs API
        self.sid = json.loads(self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.timestamp}').text[1:])['sid']
        self.last_answer = None  # Store the last response from the API
        self.history = []  # Maintain a history of queries and responses

        # Authenticate the session
        assert self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.timestamp}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}').text == 'OK'

        # Set up a secure WebSocket connection
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        self.sock = context.wrap_socket(socket.create_connection(('www.perplexity.ai', 443)), server_hostname='www.perplexity.ai')

        # Initialize WebSocket client
        self.ws = WebSocketApp(
            url=f'wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket&sid={self.sid}',
            header={'User-Agent': self.session.headers['User-Agent']},
            cookie='; '.join([f'{key}={value}' for key, value in self.session.cookies.get_dict().items()]),
            on_open=lambda ws: (ws.send('2probe'), ws.send('5')),
            on_message=self._on_message,
            on_error=lambda ws, error: print(f'Websocket Error: {error}'),
            socket=self.sock
        )

        # Run the WebSocket client in a separate thread
        Thread(target=self.ws.run_forever, daemon=True).start()

        # Wait until the WebSocket connection is established
        while not (self.ws.sock and self.ws.sock.connected):
            time.sleep(0.01)

    def _on_message(self, ws, message):
        '''
        WebSocket message handler.
        '''
        if message == '2':
            ws.send('3')  # Respond to ping messages

        if message.startswith('42'):
            response = json.loads(message[2:])[1]

            if 'final' in response:
                self.last_answer = response

    def ask(self, query, model='r1-1776', stream=False):
        '''
        Sends a query to the Perplexity Labs API.

        Parameters:
        - query: The query string.
        - model: The model to use for the query.
        - stream: Whether to stream the response.

        Returns:
        - The final response or a generator for streaming responses.
        '''
        assert model in ['r1-1776', 'sonar-pro', 'sonar', 'sonar-reasoning-pro', 'sonar-reasoning'], 'Invalid model.'

        self.last_answer = None
        self.history.append({'role': 'user', 'content': query})

        # Send the query via WebSocket
        self.ws.send('42' + json.dumps([
            'perplexity_labs',
            {
                'messages': self.history,
                'model': model,
                'source': 'default',
                'version': '2.18',
            }
        ]))

        def stream_response():
            '''
            Generator for streaming responses.
            '''
            answer = None

            while True:
                if self.last_answer != answer:
                    answer = self.last_answer
                    yield answer

                if self.last_answer and self.last_answer.get('final'):
                    answer = self.last_answer
                    self.last_answer = None
                    self.history.append({'role': 'assistant', 'content': answer['output'], 'priority': 0})

                    return

                time.sleep(0.01)

        if stream:
            return stream_response()

        while True:
            if self.last_answer and self.last_answer.get('final'):
                answer = self.last_answer
                self.last_answer = None
                self.history.append({'role': 'assistant', 'content': answer['output'], 'priority': 0})

                return answer

            time.sleep(0.01)