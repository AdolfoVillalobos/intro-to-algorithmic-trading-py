from __future__ import annotations

import logging

import colorlog


def get_logger(name: str):
    logger = logging.getLogger(name)
    handler = colorlog.StreamHandler()
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s %(levelname)-7s %(message)s%(reset)s",
        log_colors={
            "DEBUG": "blue",
            "INFO": "cyan",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger
