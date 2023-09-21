import json
import time
import requests
import random
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from bs4 import BeautifulSoup
from websocket import WebSocketApp
from uuid import uuid4
from threading import Thread

# utility function for parsing HTML content - using BeautifulSoup, lxml parser
def souper(x):
    return BeautifulSoup(x, 'lxml')

# client class for emailnator
class Emailnator:
    def __init__(self, headers, cookies, domain=False, plus=False, dot=True, google_mail=False):
        # inbox_ads for exclude the advertisements when you create a new mail
        self.inbox = []
        self.inbox_ads = []

        # create session with provided headers & cookies
        self.s = requests.Session()
        self.s.headers.update(headers)
        self.s.cookies.update(cookies)

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
        self.email = self.s.post('https://www.emailnator.com/generate-email', json=data).json()['email'][0]

        # append advertisements to inbox_ads
        for ads in self.s.post('https://www.emailnator.com/message-list', json={'email': self.email}).json()['messageData']:
            self.inbox_ads.append(ads['messageID'])

    # reload inbox messages
    def reload(self, wait=False, retry_timeout=5):
        self.new_msgs = []

        while True:
            for msg in self.s.post('https://www.emailnator.com/message-list', json={'email': self.email}).json()['messageData']:
                if msg['messageID'] not in self.inbox_ads and msg not in self.inbox:
                    self.new_msgs.append(msg)

            if wait and not self.new_msgs:
                time.sleep(retry_timeout)
            else:
                break

        self.inbox += self.new_msgs
        return self.new_msgs

    # open selected inbox message
    def open(self, msg_id):
        return self.s.post('https://www.emailnator.com/message-list', json={'email': self.email, 'messageID': msg_id}).text


# client class for interactions with perplexity ai webpage
class Client:
    def __init__(self, headers, cookies):
        self.session = requests.Session()
        self.session.headers.update(headers)
        self.session.cookies.update(cookies)
        self.session.get(f'https://www.perplexity.ai/search/{str(uuid4())}')

        # generate random values for session init
        self.t = format(random.getrandbits(32), '08x')
        self.sid = json.loads(self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}').text[1:])['sid']
        self.frontend_uuid = str(uuid4())
        self.frontend_session_id = str(uuid4())
        self._last_answer = None
        self._last_file_upload_info = None
        self.copilot = 0
        self.file_upload = 0
        self.n = 1


        assert self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}').text == 'OK'

        # setup websocket communication
        self.ws = WebSocketApp(
            url=f'wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket&sid={self.sid}',
            cookie='; '.join([f'{x}={y}' for x, y in self.session.cookies.get_dict().items()]),
            header={'user-agent': self.session.headers['user-agent']},
            on_open=lambda ws: ws.send('2probe'),
            on_message=self.on_message,
            on_error=lambda ws, err: print(f'Error: {err}'),
        )

        # start webSocket thread
        Thread(target=self.ws.run_forever).start()
        time.sleep(1)

    # method to create an account on the webpage
    def create_account(self, headers, cookies):
        emailnator_cli = Emailnator(headers, cookies, dot=False, google_mail=True)

        # send sign in link to email
        resp = self.session.post('https://www.perplexity.ai/api/auth/signin/email', data={
            'email': emailnator_cli.email,
            'csrfToken': self.session.cookies.get_dict()['next-auth.csrf-token'].split('%')[0],
            'callbackUrl': 'https://www.perplexity.ai/',
            'json': 'true',
        })

        if resp.ok:
            # get the link from mail and open, you will be signed in directly when you open link
            new_msgs = emailnator_cli.reload(wait=True)
            new_account_link = souper(emailnator_cli.open(new_msgs[0]['messageID'])).select('a')[1].get('href')

            self.session.get(new_account_link)
            self.session.get('https://www.perplexity.ai/')

            self.copilot = 5
            self.file_upload = 3

            self.ws.close()

            # generate random values for session init
            self.t = format(random.getrandbits(32), '08x')
            self.sid = json.loads(self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}').text[1:])['sid']

            assert self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}').text == 'OK'

            # reconfig - WebSocket communication
            self.ws = WebSocketApp(
                url=f'wss://www.perplexity.ai/socket.io/?EIO=4&transport=websocket&sid={self.sid}',
                cookie='; '.join([f'{x}={y}' for x, y in self.session.cookies.get_dict().items()]),
                header={'user-agent': self.session.headers['user-agent']},
                on_open=lambda ws: ws.send('2probe'),
                on_message=self.on_message,
                on_error=lambda ws, err: print(f'Error: {err}'),
            )

            # start WebSocket thread
            Thread(target=self.ws.run_forever).start()
            time.sleep(1)

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
    def search(self, query, mode='concise', focus='internet', file=None, follow_up=None, solvers={}):
        assert mode in ['concise', 'copilot'], 'Search modes --> ["concise", "copilot"]'
        assert focus in ['internet', 'scholar', 'writing', 'wolfram', 'youtube', 'reddit'], 'Search focus modes --> ["internet", "scholar", "writing", "wolfram", "youtube", "reddit"]'
        assert self.copilot > 0 if mode == 'copilot' else True, 'You have used all of your copilots'
        assert self.file_upload > 0 if file else True, 'You have used all of your file uploads'

        self.copilot = self.copilot - 1 if mode == 'copilot' else self.copilot
        self.file_upload = self.file_upload - 1 if file else self.file_upload
        self.n += 1
        self._last_answer = None
        self._last_file_upload_info = None


        if file:
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

            if not self._last_file_upload_info['success']:
                raise Exception('File upload error', self._last_file_upload_info)

            # requests_toolbelt's multipart encoder
            monitor = MultipartEncoderMonitor(MultipartEncoder(fields={
                **self._last_file_upload_info['fields'],
                'file': ('myfile', file[0], {'txt': 'text/plain', 'pdf': 'application/pdf'}[file[1]])
            }))

            if not (upload_resp := requests.post(self._last_file_upload_info['url'], data=monitor, headers={'Content-Type': monitor.content_type})).ok:
                raise Exception('File upload error', upload_resp)

            uploaded_file = self._last_file_upload_info['url'] + self._last_file_upload_info['fields']['key'].replace('${filename}', 'myfile')

            # send search request with uploaded file as an attachment
            self.ws.send(f'{420 + self.n}' + json.dumps([
                'perplexity_ask',
                query,
                {
                    'attachments': [uploaded_file],
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
                    'version': '2.1',
                    'source': 'default',
                    'mode': mode,
                    'last_backend_uuid': follow_up if type(follow_up) == str else (follow_up['backend_uuid'] if type(follow_up) == dict else None),
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
                                    'attachments': None,
                                    'last_backend_uuid': self.backend_uuid,
                                    'existing_entry_uuid': self.backend_uuid,
                                    'read_write_token': '',
                                    'search_focus': focus,
                                    'frontend_uuid': self.frontend_uuid,
                                    'step_payload': {
                                        'uuid': str(uuid4()),
                                        'step_type': 'USER_INPUT',
                                        'content': [{'content': {'text': solver(step_query['content']['description'])[:2000]}, 'type': 'USER_TEXT', 'uuid': step_query['uuid']}]
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
                                    'attachments': None,
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
                            solver_answer = solver(step_query['content']['description'], {int(x['id']): x['value'] for x in step_query['content']['options']})

                            self.ws.send(f'{420 + self.n}' + json.dumps([
                                'perplexity_step',
                                query,
                                {
                                    'version': '2.1',
                                    'source': 'default',
                                    'attachments': None,
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
                                    'attachments': None,
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
