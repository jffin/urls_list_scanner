#!/usr/bin/env python

import json
import pathlib

from yarl import URL
from typing import Union, Dict, List, Tuple, Any, Type

import asyncio
import argparse

from asyncio import AbstractEventLoop, BoundedSemaphore
from asyncio.exceptions import TimeoutError

from aiohttp import ClientSession, ClientTimeout, InvalidURL, \
    ClientConnectorError, ClientResponseError, ServerTimeoutError, TCPConnector

ASYNCIO_GATHER_TYPE: Type = Tuple[
    Union[BaseException, Any], Union[BaseException, Any],
    Union[BaseException, Any], Union[BaseException, Any], Union[BaseException, Any]
]

SIMULTANEOUS_CONCURRENT_TASKS: int = 51

USER_AGENT: str = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)' \
                  ' Chrome/85.0.4183.102 Safari/537.36'

RESULT_FILE_NAME: str = 'result.json'


class RequestManager:
    _urls: List[URL]
    _timeout: ClientTimeout
    _session: ClientSession
    headers: Dict[str, str]

    def __init__(self, urls: List[str], timeout: int = 60):
        self._urls = [URL(url) for url in urls]
        self._timeout = ClientTimeout(total=timeout)
        self._session = ClientSession(timeout=self.timeout, connector=TCPConnector(ssl=False))
        self.headers = {'User-agent': USER_AGENT}

    @classmethod
    async def create_make_requests(cls, urls: List[str], timeout: int = 60) -> ASYNCIO_GATHER_TYPE:
        obj: RequestManager = cls(urls=urls, timeout=timeout)
        return await obj.make_request()

    async def _fetch(self, url: URL, session: ClientSession, semaphore: BoundedSemaphore) -> Dict[str, Union[str, int]]:
        async with semaphore:
            result: Dict[str, str] = {'url': str(url)}
            try:
                async with session.get(url, headers=self.headers) as response:
                    content_length: str = '0'
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
            finally:
                return result

    async def make_request(self) -> ASYNCIO_GATHER_TYPE:
        asyncio_semaphore = asyncio.BoundedSemaphore(SIMULTANEOUS_CONCURRENT_TASKS)
        async with self.session as session:
            return await asyncio.gather(*[
                asyncio.ensure_future(
                    self._fetch(url=url, session=session, semaphore=asyncio_semaphore)
                ) for url in self.urls
            ], return_exceptions=True, )

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
    ap: argparse.ArgumentParser = argparse.ArgumentParser(description='scan list of urls')
    # Add the arguments to the parser
    ap.add_argument(
        '--input', type=pathlib.Path, metavar='PATH', dest='path_to_urls',
        help='Path to file with input. Example: "/wd/input.txt"',
    )

    args: argparse.Namespace = ap.parse_args()
    urls: List[str] = args.path_to_urls.read_text().splitlines()

    results: ASYNCIO_GATHER_TYPE = await RequestManager.create_make_requests(urls=urls, timeout=5)
    write_results_to_file(results)


def write_results_to_file(results: ASYNCIO_GATHER_TYPE) -> None:
    with open(RESULT_FILE_NAME, 'w') as file:
        file.write(json.dumps(results))


if __name__ == '__main__':
    loop: AbstractEventLoop = asyncio.get_event_loop()
    loop.set_debug(False)
    loop.run_until_complete(main())
