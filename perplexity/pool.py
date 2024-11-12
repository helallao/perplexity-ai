import time
from threading import Thread
from .client import Client

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