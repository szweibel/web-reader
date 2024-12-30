"""Logging configuration for the web reader application"""

import logging
import sys
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Configure logging
def setup_logging():
    # Main logger
    logger = logging.getLogger("web_reader")
    logger.setLevel(logging.DEBUG)
    
    # Console handler - INFO and above
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    
    # File handler - DEBUG and above
    debug_file = logging.FileHandler("logs/debug.log")
    debug_file.setLevel(logging.DEBUG)
    debug_file.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # Error file handler - ERROR and above
    error_file = logging.FileHandler("logs/error.log")
    error_file.setLevel(logging.ERROR)
    error_file.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # Add handlers
    logger.addHandler(console)
    logger.addHandler(debug_file)
    logger.addHandler(error_file)
    
    return logger

# Create and configure logger
logger = setup_logging()