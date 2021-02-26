#!/usr/bin/env python

import json
import pathlib
import logging

import asyncio
import argparse

from time import time
from typing import List, NamedTuple

from utils.logger_formatter import OneLineExceptionFormatter
from utils.request_manager import RequestManager
from utils.contants import DEFAULT_DEBUGGING, RESULT_FILE_NAME, ASYNCIO_GATHER_TYPE, TIMEOUT


class RunConfig(NamedTuple):
    path_to_urls: pathlib.Path
    verbose: bool = DEFAULT_DEBUGGING
    output: str = RESULT_FILE_NAME


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
