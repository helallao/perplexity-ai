import asyncio
import json
import aiohttp
import random
from bs4 import BeautifulSoup
from websocket import WebSocketApp
from uuid import uuid4
from threading import Thread

# utility function for parsing HTML content - using BeautifulSoup, lxml parser
def souper(x):
    return BeautifulSoup(x, 'lxml')

# utility function for converting aiohttp cookie_jar to dict
def cookiejar_to_dict(cookie_jar):
    new = {}

    for x in cookie_jar._cookies.values():
        for y, z in dict(x).items():
            new.update({y: z.value})

    return new

# utility function for case-sensitive header names, to convert lower case header names to upper case taken from curlconverter.com
def case_fixer(headers):
    new_headers = {}

    for key, value in headers.items():
        new_headers.update({'-'.join([word[0].upper() + word[1:] for word in key.split('-')]): value})
    
    return new_headers


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


# client class for emailnator
class Emailnator(AsyncMixin):
    async def __ainit__(self, headers, cookies, domain=False, plus=False, dot=True, google_mail=False):
        # inbox_ads for exclude the advertisements when you create a new mail
        self.inbox = []
        self.inbox_ads = []

        # create session with provided headers & cookies
        self.s = aiohttp.ClientSession(headers=headers, cookies=cookies)

        # preparing data for email generation
        data = {'email': []}
        if domain:
            data['email'].append('domain')
        if plus:
            data['email'].append('plusGmail')
        if dot:
            data['email'].append('dotGmail')
        if google_mail:
            data['email'].append('googleMail')

        # generate temporary email address
        self.email = (await (await self.s.post('https://www.emailnator.com/generate-email', json=data)).json())['email'][0]

        # append advertisements to inbox_ads
        for ads in (await (await self.s.post('https://www.emailnator.com/message-list', json={'email': self.email})).json())['messageData']:
            self.inbox_ads.append(ads['messageID'])

    # reload inbox messages
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

    # open selected inbox message
    async def open(self, msg_id):
        return (await (await self.s.post('https://www.emailnator.com/message-list', json={'email': self.email, 'messageID': msg_id})).text())


# client class for interactions with perplexity ai webpage
class Client(AsyncMixin):
    async def __ainit__(self, headers, cookies):
        self.session = aiohttp.ClientSession(headers=case_fixer(headers), cookies=cookies)

        await self.session.get(f'https://www.perplexity.ai/search/{str(uuid4())}')

        # generate random values for session init
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

        # setup websocket communication
        self.ws = WebSocketApp(
            url=f'wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket&sid={self.sid}',
            cookie='; '.join([f'{x}={y}' for x, y in cookiejar_to_dict(self.session.cookie_jar).items()]),
            header={'user-agent': self.session.headers['user-agent']},
            on_open=lambda ws: ws.send('2probe'),
            on_message=self.on_message,
            on_error=lambda ws, err: print(f'Error: {err}'),
        )

        # start webSocket thread
        Thread(target=self.ws.run_forever).start()
        await asyncio.sleep(1)

    # method to create an account on the webpage
    async def create_account(self, headers, cookies):
        emailnator_cli = await Emailnator(headers, cookies, dot=False, google_mail=True)

        # send sign in link to email
        resp = await self.session.post('https://www.perplexity.ai/api/auth/signin/email', data={
            'email': emailnator_cli.email,
            'csrfToken': cookiejar_to_dict(self.session.cookie_jar)['next-auth.csrf-token'].split('%')[0],
            'callbackUrl': 'https://www.perplexity.ai/',
            'json': 'true',
        })

        if resp.ok:
            # get the link from mail and open, you will be signed in directly when you open link
            new_msgs = await emailnator_cli.reload(wait=True)
            new_account_link = souper(await emailnator_cli.open(new_msgs[0]['messageID'])).select('a')[1].get('href')
            await emailnator_cli.s.close()

            await self.session.get(new_account_link)
            await self.session.get('https://www.perplexity.ai/')

            self.copilot = 5
            self.file_upload = 3

            self.ws.close()

            # generate random values for session init
            self.t = format(random.getrandbits(32), '08x')
            self.sid = json.loads((await (await self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}')).text())[1:])['sid']

            assert (await (await self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}')).text()) == 'OK'

            # reconfig - WebSocket communication
            self.ws = WebSocketApp(
                url=f'wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket&sid={self.sid}',
                cookie='; '.join([f'{x}={y}' for x, y in cookiejar_to_dict(self.session.cookie_jar).items()]),
                header={'user-agent': self.session.headers['user-agent']},
                on_open=lambda ws: ws.send('2probe'),
                on_message=self.on_message,
                on_error=lambda ws, err: print(f'Error: {err}'),
            )

            # start WebSocket thread
            Thread(target=self.ws.run_forever).start()
            await asyncio.sleep(1)

            return True

    # message handler function for Websocket
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

    # method to search on the webpage
    async def search(self, query, mode='concise', focus='internet', files=[], follow_up=None, solvers={}):
        assert mode in ['concise', 'copilot'], 'Search modes --> ["concise", "copilot"]'
        assert focus in ['internet', 'scholar', 'writing', 'wolfram', 'youtube', 'reddit'], 'Search focus modes --> ["internet", "scholar", "writing", "wolfram", "youtube", "reddit"]'
        assert self.copilot > 0 if mode == 'copilot' else True, 'You have used all of your copilots'
        assert self.file_upload - len(files) >= 0 if files else True, f'You have tried to upload {len(files)} files but you have {self.file_upload} file upload(s) remaining.'

        self.copilot = self.copilot - 1 if mode == 'copilot' else self.copilot
        self.file_upload = self.file_upload - len(files) if files else self.file_upload
        self.n += 1
        self._last_answer = None
        self._last_file_upload_info = None


        if files:
            if follow_up:
                raise Exception('File upload cannot be used in follow-up queries')

            uploaded_files = []

            for file_id, file in enumerate(files):
                # request an upload URL for a file
                self.ws.send(f'{420 + self.n}' + json.dumps([
                    'get_upload_url',
                    {
                        'version': '2.1',
                        'source': 'default',
                        'content_type': {'txt': 'text/plain', 'pdf': 'application/pdf'}[file[1]]
                    }
                ]))
    
                # wait for response
                while not self._last_file_upload_info:
                    pass
                self.n += 1
    
                if not self._last_file_upload_info['success']:
                    raise Exception('File upload error', self._last_file_upload_info)
    
                # aiohttp's own multipart encoder
                with aiohttp.MultipartWriter("form-data") as mp:
                    for field_name, field_value in self._last_file_upload_info['fields'].items():
                        part = mp.append(field_value)
                        part.set_content_disposition('form-data', name=field_name)
    
                    part = mp.append(file[0], {'Content-Type': {'txt': 'text/plain', 'pdf': 'application/pdf'}[file[1]]})
                    part.set_content_disposition('form-data', name='file', filename=f'myfile{file_id}')
    
                    upload_resp = await self.session.post(self._last_file_upload_info['url'], data=mp, headers={'Content-Type': mp.content_type})
    
                if not upload_resp.ok:
                    raise Exception('File upload error', upload_resp)
    
                uploaded_files.append(self._last_file_upload_info['url'] + self._last_file_upload_info['fields']['key'].replace('${filename}', f'myfile{file_id}'))

            # send search request with uploaded files as attachments
            self.ws.send(f'{420 + self.n}' + json.dumps([
                'perplexity_ask',
                query,
                {
                    'attachments': uploaded_files,
                    'version': '2.1',
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

        # send search request without file
        else:
            self.ws.send(f'{420 + self.n}' + json.dumps([
                'perplexity_ask',
                query,
                {
                    'attachments': follow_up['attachments'] if follow_up else None,
                    'version': '2.1',
                    'source': 'default',
                    'mode': mode,
                    'last_backend_uuid': follow_up['backend_uuid'] if follow_up else None,
                    'read_write_token': '',
                    'conversational_enabled': True,
                    'frontend_session_id': self.frontend_session_id,
                    'search_focus': focus,
                    'frontend_uuid': self.frontend_uuid,
                    'gpt4': False,
                    'language': 'en-US',
                }
            ]))


        # we will enter a loop here, ai will ask questions and prompt solvers will answer
        while True:
            while not self._last_answer:
                pass

            # if ai finished asking questions, return answer
            if self._last_answer['step_type'] == 'FINAL':
                return self._last_answer

            # if ai asking a question, use prompt solvers to answer
            elif self._last_answer['step_type'] == 'PROMPT_INPUT':
                self.backend_uuid = self._last_answer['backend_uuid']

                for step_query in self._last_answer['text'][-1]['content']['inputs']:
                    if step_query['type'] == 'PROMPT_TEXT':
                        solver = solvers.get('text', None)

                        # use solver to answer if solver function is defined
                        if solver:
                            self.ws.send(f'{420 + self.n}' + json.dumps([
                                'perplexity_step',
                                query,
                                {
                                    'version': '2.1',
                                    'source': 'default',
                                    'attachments': self._last_answer['attachments'],
                                    'last_backend_uuid': self.backend_uuid,
                                    'existing_entry_uuid': self.backend_uuid,
                                    'read_write_token': '',
                                    'search_focus': focus,
                                    'frontend_uuid': self.frontend_uuid,
                                    'step_payload': {
                                        'uuid': str(uuid4()),
                                        'step_type': 'USER_INPUT',
                                        'content': [{'content': {'text': (await solver(step_query['content']['description']))[:2000]}, 'type': 'USER_TEXT', 'uuid': step_query['uuid']}]
                                    }
                                }
                            ]))

                        # skip the question if solver function is not defined
                        else:
                            self.ws.send(f'{420 + self.n}' + json.dumps([
                                'perplexity_step',
                                query,
                                {
                                    'version': '2.1',
                                    'source': 'default',
                                    'attachments': self._last_answer['attachments'],
                                    'last_backend_uuid': self.backend_uuid,
                                    'existing_entry_uuid': self.backend_uuid,
                                    'read_write_token': '',
                                    'search_focus': focus,
                                    'frontend_uuid': self.frontend_uuid,
                                    'step_payload': {
                                        'uuid': str(uuid4()),
                                        'step_type': 'USER_SKIP',
                                        'content': [{'content': {'text': 'Skipped'}, 'type': 'USER_TEXT', 'uuid': step_query['uuid']}]
                                    }
                                }
                            ]))


                    if step_query['type'] == 'PROMPT_CHECKBOX':
                        solver = solvers.get('checkbox', None)

                        # use solver to answer if solver function is defined
                        if solver:
                            solver_answer = await solver(step_query['content']['description'], {int(x['id']): x['value'] for x in step_query['content']['options']})

                            self.ws.send(f'{420 + self.n}' + json.dumps([
                                'perplexity_step',
                                query,
                                {
                                    'version': '2.1',
                                    'source': 'default',
                                    'attachments': self._last_answer['attachments'],
                                    'last_backend_uuid': self.backend_uuid,
                                    'existing_entry_uuid': self.backend_uuid,
                                    'read_write_token': '',
                                    'search_focus': focus,
                                    'frontend_uuid': self.frontend_uuid,
                                    'step_payload': {
                                        'uuid': str(uuid4()),
                                        'step_type': 'USER_INPUT',
                                        'content': [{'content': {'options': [x for x in step_query['content']['options'] if int(x['id']) in solver_answer]}, 'type': 'USER_CHECKBOX', 'uuid': step_query['uuid']}]
                                    }
                                }
                            ]))

                        # skip the question if solver function is not defined
                        else:
                            self.ws.send(f'{420 + self.n}' + json.dumps([
                                'perplexity_step',
                                query,
                                {
                                    'version': '2.1',
                                    'source': 'default',
                                    'attachments': self._last_answer['attachments'],
                                    'last_backend_uuid': self.backend_uuid,
                                    'existing_entry_uuid': self.backend_uuid,
                                    'read_write_token': '',
                                    'search_focus': focus,
                                    'frontend_uuid': self.frontend_uuid,
                                    'step_payload': {
                                        'uuid': str(uuid4()),
                                        'step_type': 'USER_SKIP',
                                        'content': [{'content': {'options': []}, 'type': 'USER_CHECKBOX', 'uuid': step_query['uuid']}]
                                    }
                                }
                            ]))


            self._last_answer = None
