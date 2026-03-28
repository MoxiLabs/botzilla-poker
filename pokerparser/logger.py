import logging
import sys
import os
from logging.handlers import RotatingFileHandler

# Default constellation
DEFAULT_LOG_FILE = 'botzilla.log'
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_BACKUP_COUNT = 3
DEFAULT_LEVEL = logging.INFO

def setup_logger(name="Botzilla", log_file=DEFAULT_LOG_FILE, max_bytes=DEFAULT_MAX_BYTES, backup_count=DEFAULT_BACKUP_COUNT, level=DEFAULT_LEVEL):
    """Initializes and returns a configured logger with console and rotating file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding handlers if they already exist (e.g., during module reloads)
    if not logger.handlers:
        # Create formatter
        # format: 2024-03-28 12:00:00,000 - Botzilla - INFO - Message
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Console Handler (stdout)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File Handler (Rotating)
        try:
            # Ensure the directory for the log file exists if it's in a path
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            file_handler = RotatingFileHandler(
                log_file, 
                maxBytes=max_bytes, 
                backupCount=backup_count, 
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to initialize file logger: {e}", file=sys.stderr)

    return logger

def setup_discord_logging(log_file=DEFAULT_LOG_FILE, max_bytes=DEFAULT_MAX_BYTES, backup_count=DEFAULT_BACKUP_COUNT):
    """Sets up the 'discord' library logger to use the same file and console output."""
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.INFO) # Library default is usually too verbose at DEBUG
    
    # We don't want to re-add handlers if they already exist
    if not discord_logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # File Handler
        try:
            file_handler = RotatingFileHandler(
                log_file, 
                maxBytes=max_bytes, 
                backupCount=backup_count, 
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            discord_logger.addHandler(file_handler)
        except:
            pass
            
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        discord_logger.addHandler(console_handler)

# Create a default instance for convenience
log = logging.getLogger("Botzilla")
