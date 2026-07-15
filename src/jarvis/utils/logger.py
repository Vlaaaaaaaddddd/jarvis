import logging
import os
from pathlib import Path

log_dir = Path(__file__).parent.parent.parent.parent / "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = log_dir / "jarvis_debug.log"

def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger