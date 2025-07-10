import logging
from concurrent_log_handler import ConcurrentRotatingFileHandler
from .settings import app_config

def setup_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.handlers = []

    handler = ConcurrentRotatingFileHandler(
        app_config.LOG_FILE,
        maxBytes=app_config.MAX_BYTES,
        backupCount=app_config.BACKUP_COUNT
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))

    logger.addHandler(handler)
    return logger

logger = setup_logging()