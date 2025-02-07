import re
import json
import time
from threading import Thread
from urllib.parse import unquote
from curl_cffi import requests
from playwright.sync_api import sync_playwright
from patchright.sync_api import sync_playwright as sync_patchright
from .emailnator import Emailnator


class Driver:
    def __init__(self):
        self.signin_regex = re.compile(r'"(https://www\.perplexity\.ai/api/auth/callback/email\?callbackUrl=.*?)"')
        self.creating_new_account = False
        self.background_pages = []
        self.perplexity_headers = {}
        self.emailnator_headers = {}
    
    def account_creator(self):
        self.new_account_link = None
        
        while True:
            if not self.new_account_link:
                print('Creating new account')
                
                while True:
                    try:
                        emailnator_cli = Emailnator({**self.emailnator_headers, 'x-xsrf-token': unquote(self.emailnator_cookies['XSRF-TOKEN'])}, self.emailnator_cookies)
                        
                        resp = requests.post('https://www.perplexity.ai/api/auth/signin/email', data={
                            'email': emailnator_cli.email,
                            'csrfToken': self.perplexity_cookies['next-auth.csrf-token'].split('%')[0],
                            'callbackUrl': 'https://www.perplexity.ai/',
                            'json': 'true'},
                            headers=self.perplexity_headers,
                            cookies=self.perplexity_cookies
                        )
                        
                        if resp.ok:
                            new_msgs = emailnator_cli.reload(wait_for=lambda x: x['subject'] == 'Sign in to Perplexity', timeout=20)
                            
                            if new_msgs:
                                msg = emailnator_cli.get(func=lambda x: x['subject'] == 'Sign in to Perplexity')
                                self.new_account_link = self.signin_regex.search(emailnator_cli.open(msg['messageID'])).group(1)
                                
                                print('New account created\n')
                                break
                        
                    except Exception as e:
                        print('Account creation error', e)
                        print('Renewing emailnator cookies')
                        
                        self.emailnator_headers = None
                        self.page.goto('https://www.emailnator.com/')
                
            else:
                time.sleep(1)
    
    def intercept_request(self, route, request):
        if request.url == 'https://www.perplexity.ai/':
            response = route.fetch()
            
            if 'Just a moment...' in response.text():
                route.fulfill(response=response)
            
            else:
                if not self.perplexity_headers:
                    self.perplexity_headers = request.headers
                    self.perplexity_cookies = {x.split('=')[0]: x.split('=')[1] for x in request.headers['cookie'].split('; ')}
                    
                    route.fulfill(body=':)')
                    
                    self.background_pages.append(self.page)
                    self.page = self.browser.new_page()
                    self.page.route('**/*', self.intercept_request)
                    self.page.goto('https://www.emailnator.com/')
                
                else:
                    route.fulfill(response=response)
        
        elif request.url == 'https://www.emailnator.com/':
            response = route.fetch()
            
            if 'Just a moment...' in response.text():
                route.fulfill(response=response)
            
            else:
                if not self.emailnator_headers:
                    self.emailnator_headers = request.headers
                    self.emailnator_cookies = {x.split('=')[0]: x.split('=')[1] for x in request.headers['cookie'].split('; ')}
                    
                    Thread(target=self.account_creator).start()
                    route.fulfill(body=':)')
                    
                    self.background_pages.append(self.page)
                    self.page = self.browser.new_page()
                    self.page.route('**/*', self.intercept_request)
                    
                    for page in self.background_pages:
                        page.close()
                    
                    while not self.new_account_link:
                        self.page.wait_for_timeout(1000)
                    
                    self.page.goto(self.new_account_link)
                    self.page.goto('https://www.perplexity.ai/')
                    self.new_account_link = None
        
        elif '/rest/user/save-settings' in request.url:
            response = route.fetch()
            route.fulfill(body=response.text(), response=response)
            
            if not self.creating_new_account and json.loads(response.text())['gpt4_limit'] == 0:
                self.creating_new_account = True
                self.page = self.browser.new_page()
                self.page.route('**/*', self.intercept_request)
                
                while not self.new_account_link:
                    self.page.wait_for_timeout(1000)
                
                self.page.goto(self.new_account_link)
                self.page.goto('https://www.perplexity.ai/')
                self.new_account_link = None
        
        else:
            route.continue_()
    
    def run(self, chrome_data_dir, port=None):
        with (sync_playwright() if port else sync_patchright()) as playwright:
            if port:
                self.browser = playwright.chromium.connect_over_cdp(f'http://localhost:{port}')
            else:
                self.browser = playwright.chromium.launch_persistent_context(
                    user_data_dir=chrome_data_dir,
                    channel="chrome",
                    headless=False,
                    no_viewport=True
                )
            
            self.page = self.browser.contexts[0].new_page() if port else self.browser.new_page()
            self.background_pages.append(self.page)
            self.page.route('**/*', self.intercept_request)
            self.page.goto('https://www.perplexity.ai/')
            
            while True:
                try:
                    self.page.context.pages[-1].wait_for_timeout(1000)
                except Exception:
                    pass