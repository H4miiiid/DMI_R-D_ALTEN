import datetime
import os
import pathlib
import logging
from typing import Dict, List, Union
from enum import Enum

log_name: str = ""
logger: logging.Logger = logging.getLogger(log_name)

class LogFormatter(logging.Formatter):
    
    _LEVEL_ABBREVIATIONS: Dict[str, str] = {
        "DEBUG": "DEB",
        "INFO": "INF",
        "WARNING": "WAR",
        "ERROR": "ERR",
        "CRITICAL": "CRI"
    }
    _COLOR_RESET: str  = "\033[0m"
    _LEVEL_COLORS: Dict[str, str] = {
        "DEBUG": "\033[37m",
        "INFO": "\033[32m",
        "WARNING":"\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m"
    }
    
    def __init__(self, colored: bool = False, verbose: bool = True)->None:
        super().__init__(fmt="%(asctime)s - %(levelname)s - [%(filename)s, %(funcName)s, %(lineno)d] %(message)s" if verbose else "%(asctime)s - %(levelname)s - %(message)s")
        self._colored: bool = colored
        
    
    def formatTime(self, record: logging.LogRecord, datefmt: Union[str, None]=None):
        time: str = datetime.datetime.fromtimestamp(record.created).strftime("%d-%m-%Y %H:%M:%S")
        ms: int = int(record.msecs)
        return f"{time}.{ms:03d}"

    def format(self, record: logging.LogRecord)-> str:
        original_levelname: str = record.levelname
        record.levelname = LogFormatter._LEVEL_ABBREVIATIONS.get(record.levelname, original_levelname)
        formatted: str = super().format(record)
        record.levelname = original_levelname
        return LogFormatter._LEVEL_COLORS[record.levelname] + formatted + LogFormatter._COLOR_RESET if self._colored else formatted



def setup_logging(level: int, name: str, mode: str = "w")->None:
    global log_name
    log_name = name
    log_path: str = os.path.join(pathlib.Path(__file__).parent, "log")
    os.makedirs(log_path, exist_ok=True)
    timestamp: str = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    log_file = os.path.join(log_path, f"{timestamp}.log")

    root_logger: logging.Logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.setLevel(level * 10)

        file_handler: logging.FileHandler = logging.FileHandler(log_file, mode=mode)
        file_handler.setFormatter(LogFormatter(colored=False))

        stream_handler: logging.StreamHandler = logging.StreamHandler()
        stream_handler.setFormatter(LogFormatter(colored=True))

        root_logger.addHandler(file_handler)
        root_logger.addHandler(stream_handler)


