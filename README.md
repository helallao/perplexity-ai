# Perplexity AI

Perplexity AI is a Python module that leverages [Emailnator](https://emailnator.com/) to generate new accounts for unlimited pro queries. It supports both synchronous and asynchronous APIs, as well as a web interface for users who prefer a GUI-based approach.

## Features

- **Account Generation**: Automatically generate Gmail accounts using Emailnator.
- **Unlimited Pro Queries**: Bypass query limits by creating new accounts.
- **Web Interface**: Automate account creation and usage via a browser.
- **API Support**: Synchronous and asynchronous APIs for programmatic access.

## Installation

Install the required packages:

```bash
pip install perplexity-api perplexity-api-async
```

For the web interface, install additional dependencies:

```bash
pip install patchright playwright && patchright install chromium
```

## Usage

### Web Interface

The web interface automates account creation and usage in a browser. To use it:

```python
import os
from perplexity.driver import Driver

cli = Driver()
cli.run(rf'C:\\Users\\{os.getlogin()}\\AppData\\Local\\Google\\Chrome\\User Data')
```

To use your own Chrome instance, enable remote debugging:

1. Add `--remote-debugging-port=9222` to Chrome's shortcut target.
2. Pass the port to the `Driver.run()` method:

```python
cli.run(rf'C:\\Users\\{os.getlogin()}\\AppData\\Local\\Google\\Chrome\\User Data', port=9222)
```

### API Usage

#### Synchronous API

```python
import perplexity

client = perplexity.Client()
response = client.search('Your query here', mode='auto', sources=['web'])
print(response)
```

#### Asynchronous API

```python
import asyncio
import perplexity_async

async def main():
    client = await perplexity_async.Client()
    response = await client.search('Your query here', mode='auto', sources=['web'])
    print(response)

asyncio.run(main())
```

### Account Generation

To generate accounts, provide Emailnator cookies:

```python
emailnator_cookies = { 'your_cookies_here': 'value' }
client.create_account(emailnator_cookies)
```

## How to Get Cookies

### Perplexity

1. Log in to [Perplexity.ai](https://perplexity.ai/).
2. Open the browser's developer tools (F12).
3. Copy cookies from the network tab.

### Emailnator

1. Visit [Emailnator](https://emailnator.com/).
2. Copy cookies from the network tab.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
