# -*- coding: utf-*-
# utilities for logs
import logging
import os
import pathlib
import time

from logging.handlers import RotatingFileHandler


def create_rotating_log(name: str, path: str, log_level: str, max_mbytes: int = 5, backup_count: int = 5) -> logging.Logger:
    """
    Instantiate a logger with files rotation.
    :param name: the name
    :param path: the path of the file
    :param log_level: the root level
    :param max_mbytes: the max amount of bytes used to trigger rotation of file
    :param backup_count: the max number of archived files to keep
    :return: the logger
    """
    result: logging.Logger = logging.getLogger(name)
    path_obj: pathlib.Path = pathlib.Path(path)
    if not os.path.exists(path_obj.parent.absolute()):
        os.makedirs(path_obj.parent.absolute())
    if os.path.exists(path):
        open(path, 'w').close()
    else:
        path_obj.touch()
    # noinspection Spellchecker
    formatter: logging.Formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler: logging.Handler = RotatingFileHandler(path, maxBytes=1024 * 1024 * max_mbytes, backupCount=backup_count)
    # noinspection PyUnresolvedReferences
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    result.addHandler(file_handler)
    # noinspection PyUnresolvedReferences
    result.setLevel(log_level)
    return result


def create_console_log(name: str, log_level: str, logger: logging.Logger = None) -> logging.Logger:
    """
    Instantiate a logger with console output only.
    :param name: the name
    :param log_level: the root level
    :param logger: the optional existing logger used to attach console handler to
    :return: the logger
    """
    result: logging.Logger = logger
    if result is None:
        result = logging.getLogger(name)
    # noinspection Spellchecker
    formatter: logging.Formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler: logging.Handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    result.addHandler(console_handler)
    # noinspection PyUnresolvedReferences
    result.setLevel(log_level)
    return result


def log(message) -> None:
    """
    Print the given message with formatted time prefix like 20210106_111701: Message.
    :param message: the message
    :return:
    """
    print(time.strftime('%Y%m%d_%H%M%S', time.gmtime(time.time())) + ': ' + message)
