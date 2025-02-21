from loguru import logger
from logging.handlers import SysLogHandler


def configure_logging_to_syslog():
    handler = SysLogHandler(facility=SysLogHandler.LOG_DAEMON, address="/dev/log")
    logger.add(handler)
