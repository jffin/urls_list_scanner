#!/usr/bin/env python

import os
import json
import pathlib
import logging
from time import time
from types import TracebackType

from yarl import URL
from typing import Union, Dict, List, Tuple, Any, Type, Optional, NamedTuple

import asyncio
import argparse

from asyncio import BoundedSemaphore
from asyncio.exceptions import TimeoutError

from aiohttp import ClientSession, ClientTimeout, InvalidURL, \
    ClientConnectorError, ClientResponseError, ServerTimeoutError, TCPConnector

EXC_INFO_TYPE = Union[Tuple[type, BaseException, Optional[TracebackType]], tuple[None, None, None]]
ASYNCIO_GATHER_TYPE: Type = Tuple[
    Union[BaseException, Any], Union[BaseException, Any],
    Union[BaseException, Any], Union[BaseException, Any], Union[BaseException, Any]
]

TIMEOUT: int = 5
TIMEOUT_DEFAULT: int = 60
LIMIT_OF_ATTEMPTS_TO_RETRY: int = 5
SIMULTANEOUS_CONCURRENT_TASKS: int = 51
REQUESTS_RETRIES_NUM_TO_REMOVE = 1

DEFAULT_DEBUGGING = False

STATUS_CODE_DEFAULT, CONTENT_LENGTH_DEFAULT, STREAM_READER_DEFAULT, BODY_LENGTH_DEFAULT = 0, 0, 0, 0

USER_AGENT: str = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)' \
                  ' Chrome/85.0.4183.102 Safari/537.36'

RESULT_FILE_NAME: str = 'result.json'


class RunConfig(NamedTuple):
    path_to_urls: pathlib.Path
    verbose: bool = DEFAULT_DEBUGGING
    output: str = RESULT_FILE_NAME


class OneLineExceptionFormatter(logging.Formatter):
    def formatException(self, exc_info: EXC_INFO_TYPE) -> str:
        result = super().formatException(exc_info)
        return repr(result)

    def format(self, record: logging.LogRecord) -> str:
        result = super().format(record)
        if record.exc_text:
            result = result.replace('\n', '')
        return result

    @classmethod
    def logger_initialisation(cls, debug: bool = False) -> None:
        debug_level: bool = debug and 'DEBUG' or 'INFO'
        handler: logging.StreamHandler = logging.StreamHandler()
        formatter: OneLineExceptionFormatter = cls(logging.BASIC_FORMAT)
        handler.setFormatter(formatter)
        root: logging.Logger = logging.getLogger()
        root.setLevel(os.environ.get('LOGLEVEL', debug_level))
        root.addHandler(handler)


class RequestManager:
    _urls: List[URL]
    _timeout: ClientTimeout
    _session: ClientSession
    _semaphore: BoundedSemaphore
    _headers: Dict[str, str]
    _failed_requests_num: int

    def __init__(self, urls: List[str], timeout: int = TIMEOUT_DEFAULT):
        self._urls = [URL(url) for url in urls]
        self._timeout = ClientTimeout(total=timeout)
        self._session = ClientSession(timeout=self.timeout, connector=TCPConnector(ssl=False))
        self._semaphore = asyncio.BoundedSemaphore(SIMULTANEOUS_CONCURRENT_TASKS)
        self._headers = {'User-agent': USER_AGENT}
        self._failed_requests_num = 0

    @classmethod
    async def create_make_requests(cls, urls: List[str], timeout: int = TIMEOUT_DEFAULT) -> ASYNCIO_GATHER_TYPE:
        obj: RequestManager = cls(urls=urls, timeout=timeout)
        logging.log(logging.DEBUG, f'{obj.__class__} created')
        results = await obj.make_requests()
        logging.log(logging.DEBUG, f'Number failed results: {obj.failed_requests_num}')
        return results

    async def _fetch(self, url: URL, session: ClientSession) -> Dict[str, Union[str, int]]:
        logging.log(logging.DEBUG, f'Request to url: "{url}" stated')
        async with self.semaphore:
            result: Dict[str, str] = {'url': str(url)}
            left_of_attempts_to_retry: int = LIMIT_OF_ATTEMPTS_TO_RETRY
            while left_of_attempts_to_retry:
                try:
                    async with session.get(url, headers=self.headers) as response:
                        result.update({
                            'status_code': response.status,
                            'content_length': 'content-length' in response.headers
                                              and response.headers['content-length'] or CONTENT_LENGTH_DEFAULT,
                            'stream_reader': response.content.total_bytes,
                            'body_length': len(await response.read()),
                            'error': '',
                        })
                except (ClientConnectorError, ClientResponseError, ServerTimeoutError, TimeoutError, InvalidURL) as e:
                    logging.exception(
                        f'Failed attempt num: '
                        f'{LIMIT_OF_ATTEMPTS_TO_RETRY - left_of_attempts_to_retry + REQUESTS_RETRIES_NUM_TO_REMOVE}'
                        f'Error: {e}'
                    )
                    left_of_attempts_to_retry -= REQUESTS_RETRIES_NUM_TO_REMOVE
                    self.failed_requests_num = REQUESTS_RETRIES_NUM_TO_REMOVE
                    if not left_of_attempts_to_retry:
                        result.update({
                            'status_code': STATUS_CODE_DEFAULT,
                            'content_length': CONTENT_LENGTH_DEFAULT,
                            'stream_reader': STREAM_READER_DEFAULT,
                            'body_length': BODY_LENGTH_DEFAULT,
                            'error': e and str(e) or 'Something Went Wrong'
                        })
                    else:
                        continue
                else:
                    logging.log(
                        logging.DEBUG,
                        f'Request to url: "{url}" succeed with possible retries: {left_of_attempts_to_retry}')
                    break
            return result

    async def make_requests(self) -> ASYNCIO_GATHER_TYPE:
        async with self.session as session:
            return await asyncio.gather(*[
                asyncio.create_task(
                    self._fetch(url=url, session=session)
                ) for url in self.urls
            ])

    @property
    def urls(self) -> List[URL]:
        return self._urls

    @property
    def timeout(self) -> ClientTimeout:
        return self._timeout

    @property
    def session(self) -> ClientSession:
        return self._session

    @property
    def semaphore(self) -> BoundedSemaphore:
        return self._semaphore

    @property
    def headers(self) -> Dict[str, str]:
        return self._headers

    @property
    def failed_requests_num(self) -> int:
        return self._failed_requests_num

    @failed_requests_num.setter
    def failed_requests_num(self, num: int) -> None:
        self._failed_requests_num += num


async def main() -> None:
    args: argparse.Namespace = cli()
    config: RunConfig = define_config_from_cmd(args)

    OneLineExceptionFormatter.logger_initialisation(config.verbose)
    logging.log(logging.DEBUG, 'Main Started')

    urls: List[str] = config.path_to_urls.read_text().splitlines()
    logging.log(logging.DEBUG, f'Got {len(urls)} from file with name: {args.path_to_urls}')

    results: ASYNCIO_GATHER_TYPE = await RequestManager.create_make_requests(urls=urls, timeout=TIMEOUT)
    write_results_to_file(results)


def write_results_to_file(results: ASYNCIO_GATHER_TYPE) -> None:
    with open(RESULT_FILE_NAME, 'w') as file:
        file.write(json.dumps(results))
    logging.log(logging.DEBUG, f'Wrote results to file with name: {RESULT_FILE_NAME}')


def define_config_from_cmd(parsed_args: 'argparse.Namespace') -> RunConfig:
    """
    parsing config from args
    :param parsed_args: argparse.Namespace
    :return: RunConfig
    """
    return RunConfig(
        path_to_urls=parsed_args.path_to_urls,
        verbose=parsed_args.verbose,
        output=parsed_args.output,
    )


def cli() -> argparse.Namespace:
    """
    here we define args to run the script with
    :return: argparse.Namespace
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='scan list of urls')
    # Add the arguments to the parser
    parser.add_argument(
        '--input', type=pathlib.Path, metavar='PATH', dest='path_to_urls',
        help='Path to file with input. Example: "/wd/input.txt"',
    )
    parser.add_argument('-v', '--verbose', action='store_true', default=DEFAULT_DEBUGGING,
                        required=False, help='Verbose debug messages')
    parser.add_argument('-o', '--output', type=str, default=RESULT_FILE_NAME, required=False, help='Output file name')

    return parser.parse_args()


if __name__ == '__main__':
    try:
        start_time = time()
        asyncio.run(main(), debug=DEFAULT_DEBUGGING)
        logging.log(logging.DEBUG, f'Time consumption: {time() - start_time: 0.3f}s')
    except Exception as error:
        logging.exception(f'Failed with: {error}')
