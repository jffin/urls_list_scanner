#!/usr/bin/env python

from yarl import URL
from typing import Union, Dict, List

import json

import asyncio
import argparse

from asyncio.exceptions import TimeoutError

from aiohttp import ClientSession, ClientTimeout, InvalidURL, \
    ClientConnectorError, ClientResponseError, ServerTimeoutError, TCPConnector

REQUESTS_LIMIT = 100

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)' \
             ' Chrome/85.0.4183.102 Safari/537.36'

RESULT_FILE_NAME = 'result.json'


class RequestManager:
    _urls: List[URL]
    _timeout: ClientTimeout
    _session: ClientSession

    def __init__(self, urls: List[str], timeout: int = 60):
        self._urls = [URL(url) for url in urls]
        self._timeout = ClientTimeout(total=timeout)
        self._session = ClientSession(timeout=self.timeout, connector=TCPConnector(ssl=False))
        self.headers = {'User-agent': USER_AGENT}

    @classmethod
    async def create_make_requests(cls, urls: List[str], timeout: int = 60) -> List[Dict[str, Union[str, int]]]:
        obj = cls(urls=urls, timeout=timeout)
        return await obj.make_request()

    async def _fetch(self, url: URL, session: ClientSession) -> Dict[str, Union[str, int]]:
        result = {'url': str(url)}
        try:
            async with session.get(url, headers=self.headers) as response:
                content_length = 0
                if 'content-length' in response.headers:
                    content_length = response.headers['content-length']
                result.update({
                    'status_code': response.status,
                    'content_length': content_length,
                    'stream_reader': response.content.total_bytes,
                    'body_length': len(await response.read()),
                    'error': '',
                })
        except (ClientConnectorError, ClientResponseError, ServerTimeoutError, TimeoutError, InvalidURL) as e:
            result.update({
                'status_code': 0,
                'content_length': 0, 'stream_reader': 0, 'body_length': 0,
                'error': e and str(e) or 'Something Went Wrong'
            })
        else:
            return result

    async def make_request(self) -> List[Dict[str, Union[str, int]]]:
        async with self.session as session:
            return [await self._fetch(url=url, session=session) for url in self.urls]

    @property
    def urls(self) -> List[URL]:
        return self._urls

    @property
    def timeout(self) -> ClientTimeout:
        return self._timeout

    @property
    def session(self) -> ClientSession:
        return self._session


async def main() -> None:
    # Construct the argument parser
    ap = argparse.ArgumentParser(description='scan list of urls')
    # Add the arguments to the parser
    ap.add_argument('urls', metavar='u', type=str, nargs='+', help='list of urls')

    args = ap.parse_args()

    results = await RequestManager.create_make_requests(urls=args.urls, timeout=5)

    with open(RESULT_FILE_NAME, 'w') as result_file:
        result_file.write(json.dumps(results))


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
