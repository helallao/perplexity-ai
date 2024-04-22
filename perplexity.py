import json
import time
import requests
import random
import re
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from websocket import WebSocketApp
from uuid import uuid4
from threading import Thread

# regex for extracting sign in link from mail sent by perplexity
signin_regex = re.compile(r'"(https://www\.perplexity\.ai/api/auth/callback/email\?callbackUrl=.*?)"')

# utility function for case-sensitive header names, to convert lower case header names to upper case taken from curlconverter.com
def case_fixer(headers):
    new_headers = {}

    for key, value in headers.items():
        new_headers.update({'-'.join([word[0].upper() + word[1:] for word in key.split('-')]): value})
    
    return new_headers


# client class for emailnator
class Emailnator:
    def __init__(self, headers, cookies, domain=False, plus=False, dot=True, google_mail=False):
        # inbox_ads for exclude the advertisements when you create a new mail
        self.inbox = []
        self.inbox_ads = []

        # create session with provided headers & cookies
        self.s = requests.Session()
        self.s.headers.update(case_fixer(headers))
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
    def reload(self, wait=False, retry_timeout=1, max_retry=10):
        self.new_msgs = []
        retry_count = 0

        while True:
            for msg in self.s.post('https://www.emailnator.com/message-list', json={'email': self.email}).json()['messageData']:
                if msg['messageID'] not in self.inbox_ads and msg not in self.inbox:
                    self.new_msgs.append(msg)

            retry_count += 1

            if wait and retry_count < max_retry and not self.new_msgs:
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
                emailnator_cli = Emailnator(headers, cookies, dot=False, google_mail=True)

                # send sign in link to email
                resp = self.session.post('https://www.perplexity.ai/api/auth/signin/email', data={
                    'email': emailnator_cli.email,
                    'csrfToken': self.session.cookies.get_dict()['next-auth.csrf-token'].split('%')[0],
                    'callbackUrl': 'https://www.perplexity.ai/',
                    'json': 'true',
                })

                if resp.ok:
                    new_msgs = emailnator_cli.reload(wait=True)

                    if new_msgs:
                        break
    
                else:
                    print('Perplexity account creating error:', resp)

            except:
                pass

        # open the link received from mail, you will be signed in directly when you open link
        new_account_link = signin_regex.search(emailnator_cli.open(new_msgs[0]['messageID'])).group(1)

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
        assert focus in ['internet', 'scholar', 'writing', 'wolfram', 'youtube', 'reddit'], 'Search focus modes --> ["internet", "scholar", "writing", "wolfram", "youtube", "reddit"]'
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
                    'version': '2.2',
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
                        'version': '2.2',
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

                # requests_toolbelt's multipart encoder
                monitor = MultipartEncoderMonitor(MultipartEncoder(fields={
                    **self._last_file_upload_info['fields'],
                    'file': (f'myfile{file_id}', file[0], {'txt': 'text/plain', 'pdf': 'application/pdf'}[file[1]])
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
                    'version': '2.2',
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
                    'version': '2.2',
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
                                    'version': '2.2',
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
                                    'version': '2.2',
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
                                    'version': '2.2',
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
                                    'version': '2.2',
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


# client class for interactions with perplexity ai labs webpage
class LabsClient:
    def __init__(self, headers, cookies):
        self.session = requests.Session()
        self.session.headers.update(case_fixer(headers))
        self.session.cookies.update(cookies)

        # generate random values for session init
        self.t = format(random.getrandbits(32), '08x')
        self.sid = json.loads(self.session.get(f'https://labs-api.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}').text[1:])['sid']
        self._last_answer = None
        self.history = []

        assert self.session.post(f'https://labs-api.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}').text == 'OK'
        self.session.get(f'https://labs-api.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.t}&sid={self.sid}')

        # setup websocket communication
        self.ws = WebSocketApp(
            url=f'wss://labs-api.perplexity.ai/socket.io/?EIO=4&transport=websocket&sid={self.sid}',
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
    def ask(self, query, model='pplx-7b-online'):
        assert model in ['pplx-7b-online', 'pplx-70b-online', 'pplx-7b-chat', 'pplx-70b-chat', 'mistral-7b-instruct', 'codellama-34b-instruct', 'codellama-70b-instruct', 'llama-2-70b-chat', 'llava-7b-chat', 'mixtral-8x7b-instruct', 'mistral-medium', 'related'], 'Search modes --> ["pplx-7b-online", "pplx-70b-online", "pplx-7b-chat", "pplx-70b-chat", "mistral-7b-instruct", "codellama-34b-instruct", "codellama-70b-instruct", "llama-2-70b-chat", "llava-7b-chat", "mixtral-8x7b-instruct", "mistral-medium", "related"]'

        self._last_answer = None
        self.history.append({'role': 'user', 'content': query, 'priority': 0})

        self.ws.send('42' + json.dumps([
            'perplexity_playground',
            {
                'version': '2.2',
                'source': 'default',
                'model': {
                    'pplx-7b-online': 'pplx-7b-online',
                    'pplx-70b-online': 'pplx-70b-online',
                    'pplx-7b-chat': 'pplx-7b-chat',
                    'pplx-70b-chat': 'pplx-70b-chat',
                    'mistral-7b-instruct': 'mistral-7b-instruct',
                    'codellama-34b-instruct': 'codellama-34b-instruct',
                    'codellama-70b-instruct': 'codellama-70b-instruct',
                    'llama-2-70b-chat': 'llama-2-70b-chat',
                    'llava-7b-chat': 'llava-v1.5-7b-wrapper',
                    'mixtral-8x7b-instruct': 'mixtral-8x7b-instruct',
                    'mistral-medium': 'mistral-medium',
                    'related': 'related'}[model],
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


class Pool:
    def __init__(self, perplexity_headers, perplexity_cookies, emailnator_headers, emailnator_cookies, copilots=10, file_uploads=5, threads=1):
        self.perplexity_headers = perplexity_headers
        self.perplexity_cookies = perplexity_cookies

        self.emailnator_headers = emailnator_headers
        self.emailnator_cookies = emailnator_cookies

        self.copilots = copilots
        self.file_uploads = file_uploads
        self.accounts = []

        for _ in range(threads):
            Thread(target=self.automation).start()

    def automation(self):
        while True:
            # if copilot or file upload count is lower than self.copilots and self.file_uploads, create new account. Accounts that doesn't have copilot and file upload at the same time will be excluded becuase of calculation errors
            # let's say self.copilots is 3 and self.file_uploads is 3, and there are 2 accounts at self.accounts right now, first one has 3 copilots but 0 file uploads and second one has 3 file uploads but 0 copilots, what will happen when you use ask() function in copilot mode with file upload
            current_copilots = sum([x.copilot for x in self.accounts if x.copilot and x.file_upload])
            current_file_uploads = sum([x.file_upload for x in self.accounts if x.copilot and x.file_upload])

            if not self.accounts or current_copilots < self.copilots or current_file_uploads < self.file_uploads:
                new_account = Client(self.perplexity_headers, self.perplexity_cookies)
                new_account.create_account(self.emailnator_headers, self.emailnator_cookies)

                self.accounts.append(new_account)

                # remove accounts that doesn't has copilot and file upload at the same time if the count of copilot or file upload not going to be less than self.copilots / 2
                # so the codes below acts like garbage, but it will retain accounts that has copilot or file upload for only copilot & file upload queries. I made it like this to not waste the accounts created and reduce the account creation amount
                for account in list(self.accounts):
                    current_copilots = sum([x.copilot for x in self.accounts if x.copilot and x.file_upload])
                    current_file_uploads = sum([x.file_upload for x in self.accounts if x.copilot and x.file_upload])

                    if (account.copilot == 0 or account.file_upload == 0) and (current_copilots - account.copilot >= self.copilots / 2 or current_file_uploads - account.file_upload >= self.file_uploads / 2):
                        self.accounts.remove(account)

            else:
                time.sleep(0.1)

    def search(self, query, mode='concise', focus='internet', files=[], follow_up=None, solvers={}):
        # new accounts will be added to end of list, so the accounts in beginning of list are only copilot & file upload accounts, and if they are able to fulfill the query, they will be used.
        while True:
            for account in self.accounts:
                if (account.copilot if mode=='copilot' else True) and (account.file_upload if files else True):
                    return account.search(query=query, mode=mode, focus=focus, files=files, follow_up=follow_up, solvers=solvers)

            time.sleep(0.01)
