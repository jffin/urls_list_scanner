import os
import logging

from utils.contants import EXC_INFO_TYPE


class OneLineExceptionFormatter(logging.Formatter):
    def formatException(self, exc_info: EXC_INFO_TYPE) -> str:
        result = super().formatException(exc_info)
        return repr(result)

    def format(self, record: logging.LogRecord) -> str:
        result = super().format(record)  # todo
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
