#! /usr/bin/python3
# -*- coding: utf-*-
# Media player HTTP server

import atexit
import concurrent.futures
import logging
import os
import pathlib
import signal
import sys
import traceback

from logging.handlers import RotatingFileHandler
from media_player_config import MediaPlayerConfig
from media_player_interface import MediaPlayerInterface, MediaPlayerInterfaceImpl
from media_player_tcp_server import MediaPlayerTcpController
from event_dispatcher import EventDispatcher
from media_api import MediaPlayerController
from id_threading_utils import Executor

VERSION: str = '1.0'
# noinspection PyTypeChecker
config: MediaPlayerConfig = None
# noinspection PyTypeChecker
logger: logging.Logger = None
# noinspection PyTypeChecker
interface: MediaPlayerInterface = None
# noinspection PyTypeChecker
controller: MediaPlayerController = None
# noinspection PyTypeChecker
event_dispatcher: EventDispatcher = None
# noinspection PyTypeChecker
executor: Executor = None


def create_rotating_log(path: str) -> logging.Logger:
    """
    Create the logger with file rotation.
    :param path: the path of the main log file
    :return: the logger
    """
    global config
    result: logging.Logger = logging.getLogger("MediaPlayer")
    path_obj: pathlib.Path = pathlib.Path(path)
    if not os.path.exists(path_obj.parent.absolute()):
        os.makedirs(path_obj.parent.absolute())
    if os.path.exists(path):
        open(path, 'w').close()
    else:
        path_obj.touch()
    # noinspection Spellchecker
    formatter: logging.Formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler: logging.Handler = logging.StreamHandler()
    console_handler.setLevel(config.get_log_level())
    console_handler.setFormatter(formatter)
    result.addHandler(console_handler)
    file_handler: logging.Handler = RotatingFileHandler(path, maxBytes=1024 * 1024 * 5, backupCount=5)
    # noinspection PyUnresolvedReferences
    file_handler.setLevel(config.get_log_level())
    file_handler.setFormatter(formatter)
    result.addHandler(file_handler)
    # noinspection PyUnresolvedReferences
    result.setLevel(config.get_log_level())
    return result


def shutdown():
    """
    Clean shutdown of the HTTP server.
    :return:
    """
    global logger
    if globals().get('executor'):
        try:
            if executor:
                logger.info('Stopping executor...')
                executor.shutdown(wait=False)
        except Exception as ex3:
            logger.error('Error when shutting down the controller: %s' % ex3, file=sys.stderr)
            logger.error(ex3)
    if globals().get('controller'):
        try:
            if controller and controller.is_running():
                logger.info('Stopping controller...')
                controller.stop()
        except Exception as ex1:
            logger.error('Error when shutting down the controller: %s' % ex1, file=sys.stderr)
            logger.error(ex1)
    if globals().get('interface'):
        try:
            if interface and interface.is_running():
                logger.info('Stopping interface...')
                interface.stop()
        except Exception as ex2:
            logger.error('Error when shutting down the interface: %s' % ex2, file=sys.stderr)
            logger.error(ex2)


CONFIG_PATH = str(pathlib.Path(__file__).parent) + os.sep + 'media_player.json'


def configure():
    """
    Configure the application by creating the logger, the authentication cache, registering the signal hooks.
    :return:
    """
    global CONFIG_PATH, config, logger, interface, controller, event_dispatcher, executor
    config = MediaPlayerConfig()
    config.read(CONFIG_PATH)
    # noinspection PyUnresolvedReferences
    log_file_path: str = config.get_temp_dir() + os.sep + 'media_player.log'
    config.set_root_path(str(pathlib.Path(__file__).parent))
    logger = create_rotating_log(log_file_path)
    logger.info('Configuring...')
    atexit.register(shutdown)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    executor = Executor(logger, max_workers=2, thread_name_prefix='MediaPlayer')
    try:
        interface = MediaPlayerInterfaceImpl(logger, config, executor)
    except Exception as ex4:
        exc_type4, exc_value4, exc_traceback4 = sys.exc_info()
        traceback.print_tb(exc_traceback4, limit=6, file=sys.stderr)
        logger.error(ex4)
        sys.exit(1)
    try:
        event_dispatcher = EventDispatcher(logger, config, interface, executor)
        controller = MediaPlayerTcpController(logger, config, event_dispatcher)
        event_dispatcher.set_controller(controller)
    except Exception as ex3:
        exc_type3, exc_value3, exc_traceback3 = sys.exc_info()
        traceback.print_tb(exc_traceback3, limit=6, file=sys.stderr)
        logger.error(ex3)
        sys.exit(1)


configure()


if __name__ == '__main__':
    try:
        if controller:
            controller.start()
        interface.start()
    except TypeError as ex:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
        shutdown()
    logger.info('Application stopped')
sys.exit(0)
