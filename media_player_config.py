# -*- coding: utf-*-
# Media player configuration
import json
import os
import tempfile
import threading

from id_utils import del_none
from id_setting import Setting, Settings

TIME_FORMAT: str = '%H:%M'
TEMP_DIR_KEY: str = 'temp_dir'
TCP_PORT_KEY: str = 'tcp_port'
LOG_LEVEL_KEY: str = 'log_level'
TEST_KEY: str = 'test_enabled'
DEFAULT_LOG_LEVEL: str = 'INFO'
DEFAULT_TCP_PORT: int = 20060
DEFAULT_TEMP_DIR: str = tempfile.gettempdir() + os.sep + 'Media_player'


class MediaPlayerConfig(object):
    def __init__(self):
        """
        Initialize the configuration and its settings.
        """
        self.__file_lock: threading.Lock = threading.Lock()
        # noinspection PyTypeChecker
        self._path: str = None
        # noinspection PyTypeChecker
        self._root_path: str = None
        self._settings: Settings = Settings()
        self._settings[TEMP_DIR_KEY]: Setting[str] = Setting(DEFAULT_TEMP_DIR)
        self._settings[TCP_PORT_KEY]: Setting[int] = Setting(DEFAULT_TCP_PORT, 1, 65535)
        self._settings[LOG_LEVEL_KEY]: Setting[str] = Setting(DEFAULT_LOG_LEVEL)
        self._settings[TEST_KEY]: Setting[bool] = Setting(False)

    def clone(self):
        r: MediaPlayerConfig = MediaPlayerConfig()
        r._path = self._path
        r._settings = self._settings.clone()
        r._settings[TEMP_DIR_KEY]: Setting[str] = self._settings[TEMP_DIR_KEY].clone()
        r._settings[TCP_PORT_KEY]: Setting[int] = self._settings[TCP_PORT_KEY].clone()
        r._settings[LOG_LEVEL_KEY]: Setting[str] = self._settings[LOG_LEVEL_KEY].clone()
        r._settings[TEST_KEY]: Setting[bool] = self._settings[TEST_KEY].clone()
        return r

    def get_root_path(self) -> str:
        """
        Return the root path of the application
        :return: the path of the application
        """
        return self._root_path

    def get_temp_dir(self) -> str:
        """
        Return the path of the temporary directory.
        :return: the path of the temporary directory
        """
        return self._settings[TEMP_DIR_KEY].get_value()

    def get_tcp_port(self) -> int:
        """
        Return the TCP port of the controller.
        :return: the TCP port
        """
        return self._settings[TCP_PORT_KEY].get_value()

    def get_log_level(self) -> str:
        """
        Return the log level (debug, info, warning, error)
        :return: the log level
        """
        return self._settings[LOG_LEVEL_KEY].get_value()

    def get_settings(self) -> Settings:
        """
        Return all the settings.
        :return: the settings object
        """
        return self._settings

    def is_test(self) -> bool:
        """
        Return the flag used to activate test features.
        :return: the boolean flag
        """
        return self._settings[TEST_KEY].get_value()

    def set_root_path(self, value: str) -> None:
        """
        Set the root path of the application
        :param value: the path of the application
        """
        self._root_path = value

    def set_temp_dir(self, value: str):
        """
        Set the path of the temporary directory
        :param value: the path of the temporary directory
        :return:
        """
        if value is None or len(value) == 0:
            raise ValueError('Invalid temporary directory: ' + str(value))
        self._settings[TEMP_DIR_KEY].set_value(value)

    def set_tcp_port(self, value: int) -> None:
        """
        Set the TCP port of the controller.
        :param value: the TCP port
        :return:
        """
        if value is None or value <= 1:
            raise ValueError('Invalid TCP port: ' + str(value))
        self._settings[TCP_PORT_KEY].set_value(value)

    def set_log_level(self, value: str) -> None:
        """
        Set the log level (debug, info, warning, error)
        :param value: the log level
        :return:
        """
        if value is None or len(value) == 0:
            raise ValueError('Invalid logging level: ' + str(value))
        if not (value == 'INFO' or value == 'DEBUG' or value == 'WARNING' or value == 'ERROR' or value == 'CRITICAL'):
            raise ValueError('Invalid logging level: ' + value)
        self._settings[LOG_LEVEL_KEY].set_value(value)

    def set_test(self, value: bool) -> None:
        """
        Set the flag used to activate the test features.
        :param value: the boolean
        :return:
        """
        self._settings[TEST_KEY].set_value(value)

    def write(self, path: str = None) -> None:
        """
        Write the configuration to the file.
        :param path: the path of the file
        :return:
        """
        data = self._settings.to_json_object()
        del_none(data)
        with self.__file_lock:
            if path:
                with open(path, 'w+') as file:
                    json.dump(data, file, indent=4, sort_keys=True)
                    file.flush()
            elif self._path:
                with open(self._path, 'w+') as file:
                    json.dump(data, file, indent=4, sort_keys=True)
                    file.flush()
            else:
                raise ValueError('Path is not set when trying to write configuration')

    def read(self, path: str) -> None:
        """
        Read the configuration from the file.
        :param path: the path of the file
        :return:
        """
        self._path = path
        with self.__file_lock:
            with open(path, 'r') as file:
                data: dict = json.load(file)
                self._settings.parse(data)
