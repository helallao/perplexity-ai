# Perplexity
This module uses [emailnator](https://emailnator.com/) to generate new accounts. As you know, when you create a new account, you will have 5 pro queries. This module will generate you new gmails with [emailnator](https://emailnator.com/) and you will have unlimited pro queries.

## Requirements

<details>
<summary>Click to expand</summary>
<br>

* [curl_cffi](https://pypi.org/project/curl-cffi/)
* [websocket-client](https://pypi.org/project/websocket-client/)
* [patchright](https://pypi.org/project/patchright/) & [playwright](https://pypi.org/project/playwright/) (if you are going to use web interface)


Install requirements with:
```sh
pip install -r requirements.txt
```

or with single-line command:
```sh
pip install curl_cffi websocket-client
```

and patchright if you are going to use web interface

```sh
pip install patchright playwright && patchright install chromium
```

</details>


## How To Use Web Interface
If you're just a normal user who wants to use Perplexity Pro/Reasoning unlimited and not interested in using Perplexity API in python codes, then you can use Web Interface feature. It will simply create accounts in background for you and when you run out of copilots, the new account will automatically open in new tab. [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python#best-practices) uses [chrome user data directory](https://www.google.com/search?q=chrome+user+data+directory) to be completely undetected, it's mostly ``C:\Users\YourName\AppData\Local\Google\Chrome\User Data`` for Windows, as shown below,

```python3
import os
from perplexity.driver import Driver

cli = Driver()

cli.run(rf'C:\Users\{os.getlogin()}\AppData\Local\Google\Chrome\User Data')
```

https://github.com/user-attachments/assets/6862a53c-d574-4229-a203-0a47bba4af60

You can use your own chrome instance for Web Interface too. To do this, you need to add ``--remote-debugging-port=****`` argument to chrome execution command as [explained here](https://stackoverflow.com/a/75431084). Ok, let's hammer it home for Windows 11. Type "Chrome" to your Windows search bar, right click to Chrome, click "Open file location". You will see the shortcut of Chrome, right click it, click "Properties" and add ``--remote-debugging-port=9222`` to end of "target" section. It is ``"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222`` in my end. After setting port, you can use "port" argument of ``Driver.run()``,

```python3
import os
from perplexity.driver import Driver

cli = Driver()

cli.run(rf'C:\Users\{os.getlogin()}\AppData\Local\Google\Chrome\User Data', port=9222)
```

> [!CAUTION]
> Using existing Chrome Instance isn't completely undetected. It may enter dead loop in Cloudflare verify page. The only way to bypass it is creating a new instance (so not using "port").

## How To Use API
First thing first, [Perplexity.ai](https://perplexity.ai/) is protected by cloudflare, and [emailnator](https://emailnator.com/) too. We need to open this pages manually and get the cookies. Do not forget these cookies are temporary, so you need to renew them continuously. [Here](#how-to-get-the-cookies) how to get your cookies.

```python3
import perplexity

perplexity_headers = {
    <your headers here>
}

perplexity_cookies = { 
    <your cookies here>
}

emailnator_headers = { 
    <your headers here>
}

emailnator_cookies = { 
    <your cookies here>
}

# If you're going to use your own account, login to your account and copy headers/cookies (reload the page). Set "own" as True, and do not call "create_account" function
perplexity_cli = perplexity.Client(perplexity_headers, perplexity_cookies, own=False)
perplexity_cli.create_account(emailnator_headers, emailnator_cookies) # Creates a new gmail, so your 5 pro queries will be renewed. You can pass this one if you are going to use "auto" mode

# mode = ['auto', 'pro', 'r1', 'o3-mini']
# sources = ['web', 'scholar', 'social']
# files = a dictionary which has keys as filenames and values as file data
# stream = returns a generator when enabled and just final response when disabled
# language = ISO 639 code of language you want to use
# follow_up = last query info for follow-up queries, you can directly pass response from a query, look at second example below
# incognito = Enables incognito mode, for people who are using their own account
resp = perplexity_cli.search('Your query here', mode='auto', sources=['web'], files={'myfile.txt': open('file.txt').read()}, stream=False, language='en-US', follow_up=None, incognito=False)
print(resp)

# second example to show how to use follow-up queries and stream response
for i in perplexity_cli.search('Your query here', stream=True, follow_up=resp):
    print(i)
```


<details>
<summary><h2>Labs</h2></summary>

```python3
import perplexity

perplexity_headers = {
    <your headers here>
}

perplexity_cookies = { 
    <your cookies here>
}

labs_cli = perplexity.LabsClient(perplexity_headers, perplexity_cookies)

# model = ['sonar-pro', 'sonar', 'sonar-reasoning-pro', 'sonar-reasoning']
# stream = returns a generator when enabled and just final response when disabled
print(labs_cli.ask('Your query here', model='sonar-pro', stream=False))

for i in labs_cli.ask('Your query here', model='sonar-reasoning-pro', stream=True):
    print(i)
```

</details>

## Asynchronous API

```python3
import perplexity_async
import asyncio

perplexity_headers = { 
    <your headers here>
}

perplexity_cookies = { 
    <your cookies here> 
}

emailnator_headers = { 
    <your headers here>
}

emailnator_cookies = { 
    <your cookies here>
}


# takes a string as query, and returns a string as answer.
async def my_text_prompt_solver(query):
    return input(f'{query}: ')

# takes a string as description and a dictionary as options. Dictionary consists of ids and values. Example: {1: "Orange", 2: "Banana"}
# returns a list of integers which are ids of selected options. Let's say you selected "Banana", function should return [2]
async def my_checkbox_prompt_solver(description, options):
    print(description + '\n' + '\n'.join([str(x) + ' - ' + options[x] for x in options]))
    return [int(input('--> '))]


async def test():
    # If you're going to use your own account, login to your account and copy headers/cookies (reload the page). Set "own" as True, and do not call "create_account" function. This will deactivate copilot and file upload limit controls
    perplexity_cli = await perplexity_async.Client(perplexity_headers, perplexity_cookies, own=False)
    await perplexity_cli.create_account(emailnator_headers, emailnator_cookies) # Creates a new gmail, so your 5 copilots will be renewed. You can pass this one if you are not going to use "copilot" mode

    # modes = ['concise', 'copilot']
    # focus = ['internet', 'scholar', 'writing', 'wolfram', 'youtube', 'reddit']
    # files = file list, each element of list is tuple like this: (data, filetype) perplexity supports two file types, txt and pdf
    # follow_up = last query info for follow-up queries, you can directly pass response json from a query, look at second example below.
    # ai_model = ['default', 'claude 3.5 sonnet', 'sonar large', 'gpt-4o', 'sonar huge', 'grok-2', 'claude 3.5 haiku'] only works for own=True clients (perplexity_async.Client(..., own=True))
    # solvers, list of functions to answer questions of ai while using copilot, there are 2 type of solvers, text and checkbox. If you do not define function for a solver, questions in that solver type will be skipped
    resp = await perplexity_cli.search('Your query here', mode='copilot', focus='internet', files=[(open('myfile.txt', 'rb').read(), 'txt'), (open('myfile2.pdf', 'rb').read(), 'pdf')], ai_model='default', solvers={
        'text': my_text_prompt_solver,
        'checkbox': my_checkbox_prompt_solver
    })
    print(resp)

    # second example to show how to use follow-up queries
    # you can't use file uploads on follow-up queries
    # you can pass response json from a query directly like below
    resp2 = await perplexity_cli.search('Your query here', mode='copilot', focus='internet', follow_up=resp, solvers={
        'text': my_text_prompt_solver,
        'checkbox': my_checkbox_prompt_solver
    })
    print(resp2)

    # await perplexity_cli.create_account(emailnator_headers, emailnator_cookies) # Call this function again when you're out of copilots

asyncio.run(test())
```


<details>
<summary><h2>Asynchronous Labs</h2></summary>

Open the [Labs](https://labs.perplexity.ai/) and copy headers/cookies as explained [here](#how-to-get-the-cookies) (reload the page).
<br>
<br>

```python3
import perplexity_async

labs_headers = {
    <your headers here>
}

labs_cookies = { 
    <your cookies here>
}

async def test():
    labs_cli = await perplexity_async.LabsClient(labs_headers, labs_cookies)

    # model = ['pplx-7b-online', 'pplx-70b-online', 'pplx-7b-chat', 'pplx-70b-chat', 'mistral-7b-instruct', 'codellama-34b-instruct', 'codellama-70b-instruct', 'llama-2-70b-chat', 'llava-7b-chat', 'mixtral-8x7b-instruct', 'mistral-medium', 'related']
    print(await labs_cli.ask('hi', model='pplx-7b-online'))

    # this function adds a custom message to conversation
    # role = ['user', 'assistant']
    labs_cli.add_custom_message('msg', role='assistant')

    # this function resets the conversation
    labs_cli.clear_history()

asyncio.run(test())
```

</details>

<br>


## How To Get The Cookies
Do not forget these cookies are temporary, so you need to renew them continuously.

1. Open [emailnator](https://emailnator.com/) website. Click F12 or Ctrl+Shift+I to open inspector. Go to the "Network" tab in the inspector, check "Preserve log" button, click the "Go !" button in the website, right click the "message-list" in the Network Tab and hover on "Copy" and click to "Copy as cURL (bash)". Now go to the [curlconverter](https://curlconverter.com/python/), paste your code here. The header and cookies dictionary will appear, copy and use them in your codes.

<img src="images/emailnator.jpg">


2. Open [Perplexity.ai](https://perplexity.ai/) website. Sign out if you're signed in. Click F12 or Ctrl+Shift+I to open inspector. Go to the "Network" tab in the inspector, check "Preserve log" button, click the "Sign Up" button in the website, enter a random email and click "Continue with Email" button, right click the "email" in the Network Tab and hover on "Copy" and click to "Copy as cURL (bash)". Now go to the [curlconverter](https://curlconverter.com/python/), paste your code here. The header and cookies dictionary will appear, copy them and use in your codes.

<img src="images/perplexity1.jpg">
<img src="images/perplexity2.jpg">

3. Don't confuse the headers and cookies for [emailnator](https://emailnator.com/) and [Perplexity.ai](https://perplexity.ai/), look at [How To Use](#how-to-use) to learn how to use them.


# Thanks To
* [perplexityai](https://github.com/nathanrchn/perplexityai) by [nathanrchn](https://github.com/nathanrchn)
* [dominicOT](https://github.com/dominicOT), [Kerry1207](https://github.com/Kerry1207) and [drimeF0](https://github.com/drimeF0) for their contributions
