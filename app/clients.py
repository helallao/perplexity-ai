import perplexity
import perplexity_async


def get_sync_client(cookies):
    return perplexity.Client(cookies)


async def get_async_client(cookies):
    return await perplexity_async.Client(cookies)
