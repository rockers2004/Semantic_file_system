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

# Primary logger for the application
logger = setup_logging()
