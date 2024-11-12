import requests
import time

class Emailnator:
    def __init__(self, headers, cookies, domain=False, plus=False, dot=False, google_mail=True):
        self.inbox = []
        self.inbox_ads = []
        
        self.s = requests.Session()
        self.s.headers.update(headers)
        self.s.cookies.update(cookies)
        
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
            resp = self.s.post('https://www.emailnator.com/generate-email', json=data).json()
            
            if 'email' in resp:
                break
        
        self.email = resp['email'][0]
        
        for ads in self.s.post('https://www.emailnator.com/message-list', json={'email': self.email}).json()['messageData']:
            self.inbox_ads.append(ads['messageID'])
    
    def reload(self, wait=False, retry=5, timeout=30, wait_for=None):
        self.new_msgs = []
        start = time.time()
        wait_for_found = False
        
        while True:
            for msg in self.s.post('https://www.emailnator.com/message-list', json={'email': self.email}).json()['messageData']:
                if msg['messageID'] not in self.inbox_ads and msg not in self.inbox:
                    self.new_msgs.append(msg)
                    
                    if wait_for(msg):
                        wait_for_found = True
            
            if (wait and not self.new_msgs) or wait_for:
                if wait_for_found:
                    break
                
                if time.time() - start > timeout:
                    return
                
                time.sleep(retry)
            else:
                break
        
        self.inbox += self.new_msgs
        return self.new_msgs
    
    def open(self, msg_id):
        return self.s.post('https://www.emailnator.com/message-list', json={'email': self.email, 'messageID': msg_id}).text
    
    def get(self, func, msgs=[]):
        for msg in (msgs if msgs else self.inbox):
            if func(msg):
                return msg