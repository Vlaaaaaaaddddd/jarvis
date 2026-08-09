import logging
import os
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
DEFAULT_LOG = "jarvis.log"
MEMORY_LOG = "memory_agent.log"

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False
_handlers: dict[str, logging.FileHandler] = {}


def setup_logging() -> None:
    """Инициализирует директорию логов. Вызывается один раз при старте приложения."""
    global _initialized
    if _initialized:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    level_name = os.getenv("LOG_LEVEL", "DEBUG").upper()
    level = getattr(logging, level_name, logging.DEBUG)
    logging.getLogger("jarvis").setLevel(level)

    _initialized = True


def _get_handler(filename: str) -> logging.FileHandler:
    if filename not in _handlers:
        handler = logging.FileHandler(LOG_DIR / filename, encoding="utf-8")
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
        handler.setLevel(logging.DEBUG)
        _handlers[filename] = handler
    return _handlers[filename]


def get_logger(name: str, log_file: str = DEFAULT_LOG) -> logging.Logger:
    """
    Возвращает логгер с записью в logs/<log_file>.

    name     — короткое имя модуля ('Engine') или полное ('jarvis.core.engine')
    log_file — имя файла внутри logs/ (по умолчанию jarvis.log)
    """
    setup_logging()

    full_name = name if name.startswith("jarvis.") else f"jarvis.{name}"
    logger = logging.getLogger(full_name)

    if not logger.handlers:
        logger.addHandler(_get_handler(log_file))
        logger.propagate = False

    return logger
