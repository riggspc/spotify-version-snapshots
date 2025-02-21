from loguru import logger
from logging.handlers import SysLogHandler

def configure_logging() -> None:
    handler = SysLogHandler(facility=SysLogHandler.LOG_DAEMON, address="/dev/log")
    logger.add(handler)


def get_colorized_logger():
    return logger.opt(colors=True)
