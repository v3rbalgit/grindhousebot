import logging
from colorlog import ColoredFormatter
from typing import Optional


class Logger:
    """Centralized logging configuration for the application."""

    _instance: Optional[logging.Logger] = None

    @classmethod
    def setup(cls, name: str = "grindhouse") -> logging.Logger:
        """
        Set up and return a logger instance.
        Uses singleton pattern to ensure consistent logging across the application.
        """
        if cls._instance is None:
            formatter = ColoredFormatter(
                "%(asctime)s %(log_color)s%(levelname)-8s%(reset)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                }
            )

            handler = logging.StreamHandler()
            handler.setFormatter(formatter)

            logger = logging.getLogger(name)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)  # Default to INFO level

            # Prevent duplicate logging
            logger.propagate = False

            cls._instance = logger

        return cls._instance


# Global logger instance
logger = Logger.setup()
