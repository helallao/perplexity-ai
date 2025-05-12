# Importing necessary modules
# re: Regular expressions for pattern matching
# json: JSON parsing and serialization
# time: Time-related functions
# threading: For running background tasks
# urllib.parse: URL parsing utilities
# curl_cffi: HTTP requests
# playwright.sync_api: Synchronous Playwright API for browser automation
# patchright.sync_api: Synchronous Patchright API for undetected browser automation
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
    '''
    A driver for automating account creation and usage in Perplexity AI via a web interface.
    '''

    def __init__(self):
        # Regular expression for extracting sign-in links
        self.signin_regex = re.compile(r'"(https://www\\.perplexity\\.ai/api/auth/callback/email\\?callbackUrl=.*?)"')

        # Flags and state variables
        self.creating_new_account = False
        self.account_creator_running = False
        self.renewing_emailnator_cookies = False
        self.background_pages = []  # List of background browser pages
        self.perplexity_cookies = None  # Cookies for Perplexity AI
        self.emailnator_cookies = None  # Cookies for Emailnator

    def account_creator(self):
        '''
        Background task for creating new accounts.
        '''
        self.new_account_link = None

        while True:
            if not self.new_account_link:
                print('Creating new account')

                while True:
                    try:
                        # Initialize Emailnator client
                        emailnator_cli = Emailnator(self.emailnator_cookies, {**self.emailnator_headers, 'x-xsrf-token': unquote(self.emailnator_cookies['XSRF-TOKEN'])})

                        # Send a POST request to initiate account creation
                        resp = requests.post('https://www.perplexity.ai/api/auth/signin/email', data={
                            'email': emailnator_cli.email,
                            'csrfToken': self.perplexity_cookies['next-auth.csrf-token'].split('%')[0],
                            'callbackUrl': 'https://www.perplexity.ai/',
                            'json': 'true'},
                            headers=self.perplexity_headers,
                            cookies=self.perplexity_cookies
                        )

                        # Check if the response is successful
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

                        # Reset Emailnator cookies and wait for renewal
                        self.emailnator_cookies = None
                        self.renewing_emailnator_cookies = True

                        while not self.emailnator_cookies:
                            time.sleep(0.1)

            else:
                time.sleep(1)

    def intercept_request(self, route, request):
        '''
        Intercepts browser requests to manage cookies and account creation.
        '''
        if self.renewing_emailnator_cookies and request.url != 'https://www.emailnator.com/':
            self.page.goto('https://www.emailnator.com/')
            return

        if request.url == 'https://www.perplexity.ai/':
            response = route.fetch()

            # Extract cookies from the request
            cookies = {x.split('=')[0]: x.split('=')[1] for x in request.headers['cookie'].split('; ')}

            if not self.perplexity_cookies and 'What do you want to know?' in response.text() and 'next-auth.csrf-token' in cookies:
                self.perplexity_headers = request.headers
                self.perplexity_cookies = cookies

                route.fulfill(body=':)')

                # Open a new page for Emailnator
                self.background_pages.append(self.page)
                self.page = self.browser.new_page()
                self.page.route('**/*', self.intercept_request)
                self.page.goto('https://www.emailnator.com/')

            else:
                route.fulfill(response=response)

        elif request.url == 'https://www.emailnator.com/':
            request_will_interrupt = False

            if self.renewing_emailnator_cookies:
                request_will_interrupt = True
                self.renewing_emailnator_cookies = False

            response = route.fetch()

            # Extract cookies from the request
            cookies = {x.split('=')[0]: x.split('=')[1] for x in request.headers['cookie'].split('; ')}

            if not self.emailnator_cookies and 'Temporary Disposable Gmail | Temp Mail | Email Generator' in response.text() and 'XSRF-TOKEN' in cookies:
                self.emailnator_headers = request.headers
                self.emailnator_cookies = cookies

                route.fulfill(body=':)')

                if not self.account_creator_running:
                    self.account_creator_running = True
                    Thread(target=self.account_creator).start()

                if request_will_interrupt:
                    self.page.goto('https://www.perplexity.ai/')
                    return

                # Open a new page for Perplexity AI
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

            else:
                route.fulfill(response=response)

        elif '/rest/rate-limit' in request.url:
            route.continue_()
            gpt4_limit = request.response().json()['remaining']

            if not self.creating_new_account and gpt4_limit == 0:
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
        '''
        Launches the browser and starts intercepting requests.

        Parameters:
        - chrome_data_dir: Path to the Chrome user data directory.
        - port: Port for remote debugging (optional).
        '''
        with (sync_playwright() if port else sync_patchright()) as playwright:
            if port:
                # Connect to an existing Chrome instance
                self.browser = playwright.chromium.connect_over_cdp(f'http://localhost:{port}')
            else:
                # Launch a new Chrome instance
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