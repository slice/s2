__all__ = ['upload']

import aiohttp

ENDPOINT = 'https://mystb.in'
HEADERS = {'User-Agent': 's2/0.0.0'}


async def upload(text: str):
    async with aiohttp.ClientSession(headers=HEADERS) as sess:
        resp = await sess.post(f'{ENDPOINT}/documents', data=text)
        packet = await resp.json()
        key = packet['key']
        return f'{ENDPOINT}/{key}.txt'
