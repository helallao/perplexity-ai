import re
import json
import time
import random
import mimetypes
from uuid import uuid4
from threading import Thread
import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from websocket import WebSocketApp

from .emailnator import Emailnator

def case_fixer(headers):
    new_headers = {}

    for key, value in headers.items():
        new_headers.update({'-'.join([word[0].upper() + word[1:] for word in key.split('-')]): value})
    
    return new_headers

# client class for interactions with perplexity ai webpage
class Client:
    def __init__(self, headers, cookies, own=False):
        self.session = requests.Session()
        self.session.headers.update(case_fixer(headers))
        self.session.cookies.update(cookies)

        # generate random values for session init
        self.t = format(random.getrandbits(32), '08x')
        self.sid = json.loads(self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}').text[1:])['sid']
        self.frontend_uuid = str(uuid4())
        self.frontend_session_id = str(uuid4())
        self._last_answer = None
        self._last_file_upload_info = None
        self.own = own
        self.copilot = 0 if not own else float('inf')
        self.file_upload = 0 if not own else float('inf')
        self.n = 1
        self.signin_regex = re.compile(r'"(https://www\.perplexity\.ai/api/auth/callback/email\?callbackUrl=.*?)"')


        assert self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}').text == 'OK'

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

    # method to create an account on the webpage
    def create_account(self, headers, cookies):
        while True:
            # sometimes mails from emailnator are out of order, we will pass and create a new one if it is
            try:
                emailnator_cli = Emailnator(headers, cookies)

                # send sign in link to email
                resp = self.session.post('https://www.perplexity.ai/api/auth/signin/email', data={
                    'email': emailnator_cli.email,
                    'csrfToken': self.session.cookies.get_dict()['next-auth.csrf-token'].split('%')[0],
                    'callbackUrl': 'https://www.perplexity.ai/',
                    'json': 'true',
                })

                if resp.ok:
                    new_msgs = emailnator_cli.reload(wait_for=lambda x: x['subject'] == 'Sign in to Perplexity', timeout=30)

                    if new_msgs:
                        break
    
                else:
                    print('Perplexity account creating error:', resp)

            except:
                pass

        # open the link received from mail, you will be signed in directly when you open link
        msg = emailnator_cli.get(func=lambda x: x['subject'] == 'Sign in to Perplexity')
        new_account_link = self.signin_regex.search(emailnator_cli.open(msg['messageID'])).group(1)

        self.session.get(new_account_link)
        self.session.get('https://www.perplexity.ai/')

        self.copilot = 3
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
            header={'User-Agent': self.session.headers['User-Agent']},
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
    def search(self, query, mode='concise', focus='internet', files=[], follow_up=None, solvers={}, ai_model='default'):
        assert mode in ['concise', 'copilot'], 'Search modes --> ["concise", "copilot"]'
        assert focus in ['internet', 'scholar', 'wolfram', 'writing', 'youtube', 'reddit'], 'Search focus modes --> ["internet", "scholar", "wolfram", "writing", "youtube", "reddit"]'
        assert ai_model in ['default', 'experimental', 'gpt-4', 'claude-2.1', 'gemini pro'], 'Ai models --> ["default", "experimental", "gpt-4", "claude-2.1", "gemini pro"]'
        assert self.copilot > 0 if mode == 'copilot' else True, 'You have used all of your copilots'
        assert self.file_upload - len(files) >= 0 if files else True, f'You have tried to upload {len(files)} files but you have {self.file_upload} file upload(s) remaining.'

        self.copilot = self.copilot - 1 if mode == 'copilot' else self.copilot
        self.file_upload = self.file_upload - len(files) if files else self.file_upload
        self.n += 1
        self._last_answer = None
        self._last_file_upload_info = None

        # set ai model
        if self.own:
            self.ws.send(f'{420 + self.n}' + json.dumps([
                'save_user_settings',
                {
                    'version': '2.13',
                    'source': 'default',
                    'default_model': {
                        'default': 'turbo',
                        'experimental': 'experimental',
                        'gpt-4': 'gpt4',
                        'claude-2.1': 'claude2',
                        'gemini pro': 'gemini'}[ai_model]
                }
            ]))
            self.n += 1


        if files:
            if follow_up:
                raise Exception('File upload cannot be used in follow-up queries')

            uploaded_files = []

            for file_id, file in enumerate(files):
                # request an upload URL for a file
                self.ws.send(f'{420 + self.n}' + json.dumps([
                    'get_upload_url',
                    {
                        'version': '2.13',
                        'source': 'default',
                        'content_type': mimetypes.guess_type('x.' + file[1])[0]
                    }
                ]))

                # wait for response
                while not self._last_file_upload_info:
                    pass
                self.n += 1

                if not self._last_file_upload_info['success']:
                    raise Exception('File upload error', self._last_file_upload_info)

                # requests_toolbelt's multipart encoder
                monitor = MultipartEncoderMonitor(MultipartEncoder(fields={
                    **self._last_file_upload_info['fields'],
                    'file': (f'myfile{file_id}', file[0], mimetypes.guess_type('x.' + file[1])[0])
                }))

                if not (upload_resp := requests.post(self._last_file_upload_info['url'], data=monitor, headers={'Content-Type': monitor.content_type})).ok:
                    raise Exception('File upload error', upload_resp)

                uploaded_files.append(self._last_file_upload_info['url'] + self._last_file_upload_info['fields']['key'].replace('${filename}', f'myfile{file_id}'))

            # send search request with uploaded files as attachments
            self.ws.send(f'{420 + self.n}' + json.dumps([
                'perplexity_ask',
                query,
                {
                    'attachments': uploaded_files,
                    'version': '2.13',
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
                    'version': '2.13',
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
                                    'version': '2.13',
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
                                    'version': '2.13',
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
                            solver_answer = solver(step_query['content']['description'], {int(x['id']): x['value'] for x in step_query['content']['options']})

                            self.ws.send(f'{420 + self.n}' + json.dumps([
                                'perplexity_step',
                                query,
                                {
                                    'version': '2.13',
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
                                    'version': '2.13',
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