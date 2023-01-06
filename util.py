import logging
from colorlog import ColoredFormatter


def setup_logger(name):
  """Return a logger with a default ColoredFormatter."""

  formatter = ColoredFormatter(
    "%(bold)s%(asctime)s%(reset)s %(bold)s%(log_color)s%(levelname)-8s%(reset)s %(purple)s%(module)s%(reset)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    reset=True,
    log_colors={
        "DEBUG": "white",
        "INFO": "blue",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bg_red",
    },
  )

  handler = logging.StreamHandler()
  handler.setFormatter(formatter)

  logger = logging.getLogger(name)
  logger.addHandler(handler)
  logger.setLevel(logging.DEBUG)

  return logger