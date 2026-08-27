"""Logging configuration and utilities for Botzilla with colorized console and robust file handlers."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional


class ColoredConsoleFormatter(logging.Formatter):
    """Custom formatter applying ANSI color codes based on log level for console output."""

    COLORS = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[32m",      # Green
        logging.WARNING: "\033[33m",   # Yellow
        logging.ERROR: "\033[31m",     # Red
        logging.CRITICAL: "\033[35;1m",# Magenta Bold
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        log_fmt = f"%(asctime)s - {color}%(levelname)-8s{self.RESET} - %(name)s - %(message)s"
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def setup_logger(
    name: str = "Botzilla",
    log_file: str = "botzilla.log",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
    level: int = logging.INFO,
) -> logging.Logger:
    """Initializes and returns a configured logger with colored console and rotating file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        # 1. Console Handler with ANSI Color formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredConsoleFormatter())
        logger.addHandler(console_handler)

        # 2. File Handler (Rotating) with detailed context (filename:lineno)
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            file_formatter = logging.Formatter(
                "%(asctime)s - %(levelname)-8s - %(name)s - [%(filename)s:%(lineno)d] - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to initialize file logger: {e}", file=sys.stderr)

    return logger


def setup_discord_logging(
    log_file: str = "botzilla.log",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
):
    """Sets up the 'discord' library logger with the same file and console output."""
    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(logging.INFO)

    if not discord_logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredConsoleFormatter())
        discord_logger.addHandler(console_handler)

        try:
            file_formatter = logging.Formatter(
                "%(asctime)s - %(levelname)-8s - %(name)s - [%(filename)s:%(lineno)d] - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(file_formatter)
            discord_logger.addHandler(file_handler)
        except Exception:
            pass


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """Logs any uncaught exceptions to the root logger before terminating."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    log.critical("Uncaught fatal exception:", exc_info=(exc_type, exc_value, exc_traceback))


def install_exception_handler():
    """Install global sys.excepthook to log unhandled crashes."""
    sys.excepthook = handle_uncaught_exception


def get_logger(name: str = "Botzilla") -> logging.Logger:
    """Convenience getter for loggers."""
    return logging.getLogger(name)


# Default logger instance
log = get_logger("Botzilla")
install_exception_handler()
