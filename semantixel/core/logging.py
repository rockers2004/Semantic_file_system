import logging
import sys
import os

def setup_logging(level=logging.INFO):
    """
    Sets up a centralized logging configuration for the entire application.
    """
    logger = logging.getLogger("semantixel")
    logger.setLevel(level)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(console_handler)
    
    # Optional: File Handler for production
    log_file = os.getenv("SEMANTIXEL_LOG_FILE")
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def log_exception(logger_instance, message: str, *args, **kwargs):
    """Log an exception with traceback at ERROR level.

    Usage::

        log_exception(logger, "Failed to process %s", file_path)
    """
    logger_instance.exception(message, *args, **kwargs)


# Primary logger for the application
logger = setup_logging()
