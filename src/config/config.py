import logging
import os
from pathlib import Path

# Directories
BASE_DIR = Path(__file__).parent.parent.absolute()
CONFIG_DIR = Path(BASE_DIR, "config")
LOGS_DIR = Path(BASE_DIR.parent, "logs")

# Создаем директории, если они не существуют
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

#Logging
FORMAT = '%(asctime)s:%(levelname)s:%(message)s'
LEVEL_LOG = logging.INFO
LOG_FILE = Path(LOGS_DIR, 'app.log')

# UI
FONT_SIZE = 8