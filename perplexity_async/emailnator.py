import time
import asyncio
from urllib.parse import unquote
from curl_cffi import requests


# https://dev.to/akarshan/asynchronous-python-magic-how-to-create-awaitable-constructors-with-asyncmixin-18j5
# https://web.archive.org/web/20230915163459/https://dev.to/akarshan/asynchronous-python-magic-how-to-create-awaitable-constructors-with-asyncmixin-18j5
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

class Emailnator(AsyncMixin):
    async def __ainit__(self, cookies, headers={}, domain=False, plus=False, dot=False, google_mail=True):
        self.inbox = []
        self.inbox_ads = []
        
        if not headers:
            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'dnt': '1',
                'origin': 'https://www.emailnator.com',
                'priority': 'u=1, i',
                'referer': 'https://www.emailnator.com/',
                'sec-ch-ua': '"Not;A=Brand";v="24", "Chromium";v="128"',
                'sec-ch-ua-arch': '"x86"',
                'sec-ch-ua-bitness': '"64"',
                'sec-ch-ua-full-version': '"128.0.6613.120"',
                'sec-ch-ua-full-version-list': '"Not;A=Brand";v="24.0.0.0", "Chromium";v="128.0.6613.120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-model': '""',
                'sec-ch-ua-platform': '"Windows"',
                'sec-ch-ua-platform-version': '"19.0.0"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
                'x-requested-with': 'XMLHttpRequest',
                'x-xsrf-token': unquote(cookies['XSRF-TOKEN']),
            }
        
        self.s = requests.AsyncSession(headers=headers, cookies=cookies, impersonate='chrome')
        
        data = {'email': []}
        
        if domain:
            data['email'].append('domain')
        if plus:
            data['email'].append('plusGmail')
        if dot:
            data['email'].append('dotGmail')
        if google_mail:
            data['email'].append('googleMail')
        
        while True:
            resp = (await self.s.post('https://www.emailnator.com/generate-email', json=data)).json()
            
            if 'email' in resp:
                break
        
        self.email = resp['email'][0]
        
        for ads in (await self.s.post('https://www.emailnator.com/message-list', json={'email': self.email})).json()['messageData']:
            self.inbox_ads.append(ads['messageID'])
    
    async def reload(self, wait=False, retry=5, timeout=30, wait_for=None):
        self.new_msgs = []
        start = time.time()
        wait_for_found = False
        
        while True:
            for msg in (await self.s.post('https://www.emailnator.com/message-list', json={'email': self.email})).json()['messageData']:
                if msg['messageID'] not in self.inbox_ads and msg not in self.inbox:
                    self.new_msgs.append(msg)
                    
                    if wait_for(msg):
                        wait_for_found = True
            
            if (wait and not self.new_msgs) or wait_for:
                if wait_for_found:
                    break
                
                if time.time() - start > timeout:
                    return
                
                await asyncio.sleep(retry)
            else:
                break
        
        self.inbox += self.new_msgs
        return self.new_msgs
    
    async def open(self, msg_id):
        return (await self.s.post('https://www.emailnator.com/message-list', json={'email': self.email, 'messageID': msg_id})).text
    
    def get(self, func, msgs=[]):
        for msg in (msgs if msgs else self.inbox):
            if func(msg):
                return msg