import asyncio
import json
import aiohttp
import random
from bs4 import BeautifulSoup
from websocket import WebSocketApp
from uuid import uuid4
from threading import Thread


def souper(x):
    return BeautifulSoup(x, 'lxml')

def cookiejar_to_dict(cookie_jar):
    new = {}

    for x in cookie_jar._cookies.values():
        for y, z in dict(x).items():
            new.update({y: z.value})

    return new



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
    async def __ainit__(self, headers, cookies, domain=False, plus=False, dot=True, google_mail=False):
        self.inbox = []
        self.inbox_ads = []

        self.s = aiohttp.ClientSession(headers=headers, cookies=cookies)

        data = {'email': []}

        if domain:
            data['email'].append('domain')
        if plus:
            data['email'].append('plusGmail')
        if dot:
            data['email'].append('dotGmail')
        if google_mail:
            data['email'].append('googleMail')

        response = await (await self.s.post('https://www.emailnator.com/generate-email', json=data)).json()
        self.email = response['email'][0]


        for ads in (await (await self.s.post('https://www.emailnator.com/message-list', json={'email': self.email})).json())['messageData']:
            self.inbox_ads.append(ads['messageID'])

    async def reload(self, wait=False, retry_timeout=5):
        self.new_msgs = []

        while True:
            for msg in (await (await self.s.post('https://www.emailnator.com/message-list', json={'email': self.email})).json())['messageData']:
                if msg['messageID'] not in self.inbox_ads and msg not in self.inbox:
                    self.new_msgs.append(msg)

            if wait and not self.new_msgs:
                await asyncio.sleep(retry_timeout)
            else:
                break

        self.inbox += self.new_msgs
        return self.new_msgs

    async def open(self, msg_id):
        return (await (await self.s.post('https://www.emailnator.com/message-list', json={'email': self.email, 'messageID': msg_id})).text())



class Client(AsyncMixin):
    async def __ainit__(self, headers, cookies):
        self.session = aiohttp.ClientSession(headers=headers, cookies=cookies)

        await self.session.get(f'https://www.perplexity.ai/search/{str(uuid4())}')

        self.t = format(random.getrandbits(32), '08x')
        self.sid = json.loads((await (await self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}')).text())[1:])['sid']
        self.frontend_uuid = str(uuid4())
        self.frontend_session_id = str(uuid4())
        self._last_answer = None
        self._last_file_upload_info = None
        self.copilot = 0
        self.file_upload = 0
        self.n = 1

        assert (await (await self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}')).text()) == 'OK'

        self.ws = WebSocketApp(
            url=f'wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket&sid={self.sid}',
            cookie='; '.join([f'{x}={y}' for x, y in cookiejar_to_dict(self.session.cookie_jar).items()]),
            header={'user-agent': self.session.headers['user-agent']},
            on_open=lambda ws: ws.send('2probe'),
            on_message=self.on_message,
            on_error=lambda ws, err: print(f'Error: {err}'),
        )

        Thread(target=self.ws.run_forever).start()
        await asyncio.sleep(1)

    async def create_account(self, headers, cookies):
        emailnator_cli = await Emailnator(headers, cookies, dot=False, google_mail=True)

        resp = await self.session.post('https://www.perplexity.ai/api/auth/signin/email', data={
            'email': emailnator_cli.email,
            'csrfToken': cookiejar_to_dict(self.session.cookie_jar)['next-auth.csrf-token'].split('%')[0],
            'callbackUrl': 'https://www.perplexity.ai/',
            'json': 'true',
        })

        if resp.ok:
            new_msgs = await emailnator_cli.reload(wait=True)
            new_account_link = souper(await emailnator_cli.open(new_msgs[0]['messageID'])).select('a')[1].get('href')
            await emailnator_cli.s.close()

            await self.session.get(new_account_link)
            await self.session.get('https://www.perplexity.ai/')

            self.copilot = 5
            self.file_upload = 3

            self.ws.close()

            self.t = format(random.getrandbits(32), '08x')
            self.sid = json.loads((await (await self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}')).text())[1:])['sid']


            assert (await (await self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}')).text()) == 'OK'

            self.ws = WebSocketApp(
                url=f'wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket&sid={self.sid}',
                cookie='; '.join([f'{x}={y}' for x, y in cookiejar_to_dict(self.session.cookie_jar).items()]),
                header={'user-agent': self.session.headers['user-agent']},
                on_open=lambda ws: ws.send('2probe'),
                on_message=self.on_message,
                on_error=lambda ws, err: print(f'Error: {err}'),
            )

            Thread(target=self.ws.run_forever).start()
            await asyncio.sleep(1)

            return True

    def on_message(self, ws, message):
        if message == '2':
            ws.send('3')
        elif message == '3probe':
            ws.send('5')


        if message.startswith(str(430 + self.n)):
            response = json.loads(message[3:])[0]

            if 'text' in response:
                response['text'] = json.loads(response['text'])
                self._last_answer = response

            else:
                self._last_file_upload_info = response

    async def search(self, query, mode='concise', focus='internet', file=None):
        assert mode in ['concise', 'copilot'], 'Search modes --> ["concise", "copilot"]'
        assert focus in ['internet', 'scholar', 'writing', 'wolfram', 'youtube', 'reddit', 'wikipedia'], 'Search focus modes --> ["internet", "scholar", "writing", "wolfram", "youtube", "reddit", "wikipedia"]'
        assert self.copilot > 0 if mode == 'copilot' else True, 'You have used all of your copilots'
        assert self.file_upload > 0 if file else True, 'You have used all of your file uploads'

        self.copilot = self.copilot - 1 if mode == 'copilot' else self.copilot
        self.file_upload = self.file_upload - 1 if file else self.file_upload
        self.n += 1
        self._last_answer = None
        self._last_file_upload_info = None

        if file:
            self.ws.send(f'{420 + self.n}' + json.dumps([
                'get_upload_url',
                {
                    'version': '2.0',
                    'source': 'default',
                    'content_type': {'txt': 'text/plain', 'pdf': 'application/pdf'}[file[1]]
                }
            ]))

            while not self._last_file_upload_info:
                pass

            if not self._last_file_upload_info['success']:
                raise Exception('File upload error', self._last_file_upload_info)


            with aiohttp.MultipartWriter("form-data") as mp:
                for field_name, field_value in self._last_file_upload_info['fields'].items():
                    part = mp.append(field_value)
                    part.set_content_disposition('form-data', name=field_name)

                part = mp.append(file[0], {'Content-Type': {'txt': 'text/plain', 'pdf': 'application/pdf'}[file[1]]})
                part.set_content_disposition('form-data', name='file', filename='myfile')

                upload_resp = await self.session.post(self._last_file_upload_info['url'], data=mp, headers={'Content-Type': mp.content_type})

            if not upload_resp.ok:
                raise Exception('File upload error', upload_resp)

            uploaded_file = self._last_file_upload_info['url'] + self._last_file_upload_info['fields']['key'].replace('${filename}', 'myfile')


            self.ws.send(f'{420 + self.n}' + json.dumps([
                'perplexity_ask',
                query,
                {
                    'attachments': [uploaded_file],
                    'version': '2.0',
                    'source': 'default',
                    'mode': mode,
                    'last_backend_uuid': None,
                    'read_write_token': '',
                    'conversational_enabled': True,
                    'frontend_session_id': self.frontend_session_id,
                    'search_focus': focus,
                    'frontend_uuid': self.frontend_uuid,
                    'gpt4': False,
                    'language': 'en-US',
                }
            ]))

        else:
            self.ws.send(f'{420 + self.n}' + json.dumps([
                'perplexity_ask',
                query,
                {
                    'version': '2.0',
                    'source': 'default',
                    'mode': mode,
                    'last_backend_uuid': None,
                    'read_write_token': '',
                    'conversational_enabled': True,
                    'frontend_session_id': self.frontend_session_id,
                    'search_focus': focus,
                    'frontend_uuid': self.frontend_uuid,
                    'gpt4': False,
                    'language': 'en-US',
                }
            ]))

        while not self._last_answer:
            pass

        return self._last_answer