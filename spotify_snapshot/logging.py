from loguru import logger
from typing import Any  # Had a really hard time typing Logger. Cheating for now
from logging.handlers import SysLogHandler

def configure_logging() -> None:
    handler = SysLogHandler(facility=SysLogHandler.LOG_DAEMON, address="/dev/log")
    logger.add(handler)


def get_colorized_logger() -> Any:  
    return logger.opt(colors=True)
