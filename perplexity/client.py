import re
import sys
import json
import random
import mimetypes
from uuid import uuid4
from curl_cffi import requests, CurlMime

from .emailnator import Emailnator


class Client:
    '''
    A client for interacting with the Perplexity AI API.
    '''
    def __init__(self, cookies={}):
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
        }, cookies=cookies)
        self.own = bool(cookies)
        self.copilot = 0 if not cookies else float('inf')
        self.file_upload = 0 if not cookies else float('inf')
        self.signin_regex = re.compile(r'"(https://www\.perplexity\.ai/api/auth/callback/email\?callbackUrl=.*?)"')
        self.timestamp = format(random.getrandbits(32), '08x')
        self.sid = json.loads(self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.timestamp}').text[1:])['sid']
        
        assert self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.timestamp}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}').text == 'OK'
        self.session.get('https://www.perplexity.ai/api/auth/session')
    
    def create_account(self, cookies):
        '''
        Function to create a new account
        '''
        while True:
            try:
                emailnator_cli = Emailnator(cookies)
                
                resp = self.session.post('https://www.perplexity.ai/api/auth/signin/email', data={
                    'email': emailnator_cli.email,
                    'csrfToken': self.session.cookies.get_dict()['next-auth.csrf-token'].split('%')[0],
                    'callbackUrl': 'https://www.perplexity.ai/',
                    'json': 'true'
                })
                
                if resp.ok:
                    new_msgs = emailnator_cli.reload(wait_for=lambda x: x['subject'] == 'Sign in to Perplexity', timeout=20)
                    
                    if new_msgs:
                        break
                else:
                    print('Perplexity account creating error:', resp)
            
            except Exception:
                pass
        
        msg = emailnator_cli.get(func=lambda x: x['subject'] == 'Sign in to Perplexity')
        new_account_link = self.signin_regex.search(emailnator_cli.open(msg['messageID'])).group(1)
        
        self.session.get(new_account_link)
        
        self.copilot = 5
        self.file_upload = 10
        
        self.sid = json.loads(self.session.get(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.timestamp}').text[1:])['sid']
        
        assert self.session.post(f'https://www.perplexity.ai/socket.io/?EIO=4&transport=polling&t={self.timestamp}&sid={self.sid}', data='40{"jwt":"anonymous-ask-user"}').text == 'OK'
        
        return True
    
    def search(self, query, mode='auto', model=None, sources=['web'], files={}, stream=False, language='en-US', follow_up=None, incognito=False):
        '''
        Query function
        '''
        assert mode in ['auto', 'pro', 'reasoning', 'deep research'], 'Search modes -> ["auto", "pro", "reasoning", "deep research"]'
        assert model in {
            'auto': [None],
            'pro': [None, 'sonar', 'gpt-4.5', 'gpt-4o', 'claude 3.7 sonnet', 'gemini 2.0 flash', 'grok-2'],
            'reasoning': [None, 'r1', 'o3-mini', 'claude 3.7 sonnet'],
            'deep research': [None]
        }[mode] if self.own else True, '''Models for modes -> {
    'auto': [None],
    'pro': [None, 'sonar', 'gpt-4.5', 'gpt-4o', 'claude 3.7 sonnet', 'gemini 2.0 flash', 'grok-2'],
    'reasoning': [None, 'r1', 'o3-mini', 'claude 3.7 sonnet'],
    'deep research': [None]
}'''
        assert all([source in ('web', 'scholar', 'social') for source in sources]), 'Sources -> ["web", "scholar", "social"]'
        assert self.copilot > 0 if mode in ['pro', 'reasoning', 'deep research'] else True, 'You have used all of your enhanced (pro) queries'
        assert self.file_upload - len(files) >= 0 if files else True, f'You have tried to upload {len(files)} files but you have {self.file_upload} file upload(s) remaining.'
        
        self.copilot = self.copilot - 1 if mode in ['pro', 'reasoning', 'deep research'] else self.copilot
        self.file_upload = self.file_upload - len(files) if files else self.file_upload
        
        uploaded_files = []
        
        for filename, file in files.items():
            file_upload_info = self.session.post('https://www.perplexity.ai/rest/uploads/create_upload_url?version=2.18&source=default', json={
                'content_type': mimetypes.guess_type(filename)[0],
                'file_size': sys.getsizeof(file),
                'filename': filename,
                'force_image': False,
                'source': 'default',
            }).json()
            
            mp = CurlMime()
            
            for key, value in file_upload_info['fields'].items():
                mp.addpart(name=key, data=value)
            
            mp.addpart(name='file', content_type=mimetypes.guess_type(filename)[0], filename=filename, data=file)
            
            upload_resp = self.session.post(file_upload_info['s3_bucket_url'], multipart=mp)
            
            if not upload_resp.ok:
                raise Exception('File upload error', upload_resp)
            
            uploaded_files.append(upload_resp.json()['secure_url'])
        
        json_data = {
            'query_str': query,
            'params':
                {
                    'attachments': uploaded_files + follow_up['attachments'] if follow_up else uploaded_files,
                    'frontend_context_uuid': str(uuid4()),
                    'frontend_uuid': str(uuid4()),
                    'is_incognito': incognito,
                    'language': language,
                    'last_backend_uuid': follow_up['backend_uuid'] if follow_up else None,
                    'mode': 'concise' if mode == 'auto' else 'copilot',
                    'model_preference': {
                        'auto': {
                            None: 'turbo'
                        },
                        'pro': {
                            None: 'pplx_pro',
                            'sonar': 'experimental',
                            'gpt-4.5': 'gpt45',
                            'gpt-4o': 'gpt4o',
                            'claude 3.7 sonnet': 'claude2',
                            'gemini 2.0 flash': 'gemini2flash',
                            'grok-2': 'grok'
                        },
                        'reasoning': {
                            None: 'pplx_reasoning',
                            'r1': 'r1',
                            'o3-mini': 'o3mini',
                            'claude 3.7 sonnet': 'claude37sonnetthinking'
                        },
                        'deep research': {
                            None: 'pplx_alpha'
                        }
                    }[mode][model],
                    'source': 'default',
                    'sources': sources,
                    'version': '2.18'
                }
            }
        
        resp = self.session.post('https://www.perplexity.ai/rest/sse/perplexity_ask', json=json_data, stream=True)
        chunks = []
        
        def stream_response(resp):
            for chunk in resp.iter_lines(delimiter=b'\r\n\r\n'):
                content = chunk.decode('utf-8')
                
                if content.startswith('event: message\r\n'):
                    content_json = json.loads(content[len('event: message\r\ndata: '):])
                    content_json['text'] = json.loads(content_json['text'])
                    
                    chunks.append(content_json)
                    yield chunks[-1]
                
                elif content.startswith('event: end_of_stream\r\n'):
                    return
        
        if stream:
            return stream_response(resp)
        
        for chunk in resp.iter_lines(delimiter=b'\r\n\r\n'):
            content = chunk.decode('utf-8')
            
            if content.startswith('event: message\r\n'):
                content_json = json.loads(content[len('event: message\r\ndata: '):])
                content_json['text'] = json.loads(content_json['text'])
                
                chunks.append(content_json)
            
            elif content.startswith('event: end_of_stream\r\n'):
                return chunks[-1]