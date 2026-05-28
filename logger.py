import logging
import sys

from config import settings


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = []
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)

    if settings.log_json:
        try:
            from pythonjsonlogger import jsonlogger

            fmt = jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        except ImportError:
            fmt = logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
    else:
        fmt = logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console.setFormatter(fmt)
    handlers.append(console)

    logging.basicConfig(level=level, handlers=handlers, force=True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
