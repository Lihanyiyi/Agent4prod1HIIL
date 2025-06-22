import logging
from concurrent_log_handler import ConcurrentRotatingFileHandler
from .settings import settings

def setup_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.handlers = []

    handler = ConcurrentRotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=settings.MAX_BYTES,
        backupCount=settings.BACKUP_COUNT
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))

    logger.addHandler(handler)
    return logger


logger = setup_logging()