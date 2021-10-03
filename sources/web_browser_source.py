# -*- coding: utf-*-
# Web browser Media definition
import json
import logging
import os
import platform
import sys

from typing import Any, Dict
from media_api import MediaSource, MediaPlayerInterface
from media_player_config import MediaPlayerConfig
from id_threading_utils import Executor
from cefpython3 import cefpython as cef

sys.excepthook = cef.ExceptHook

if platform.system() in ("Linux", "Darwin"):
    WindowUtils = cef.WindowUtils()
    WindowUtils.InstallX11ErrorHandlers()


class WebBrowserClientHandler:
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, source):
        if not WebBrowserClientHandler.__logger:
            WebBrowserClientHandler.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                WebBrowserClientHandler.__logger.addHandler(handler)
            WebBrowserClientHandler.__logger.setLevel(parent_logger.level)
        self.__source = source

    # noinspection PyPep8Naming
    def OnPreKeyEvent(self, browser, event, event_handle, is_keyboard_shortcut_out):
        WebBrowserClientHandler.__logger.debug("KeyboardHandler::OnPreKeyEvent")
        if event['type'] == cef.KEYEVENT_KEYUP :
            WebBrowserClientHandler.__logger.debug(str(event))
            WebBrowserClientHandler.__logger.debug(str(event_handle))
            WebBrowserClientHandler.__logger.debug(str(is_keyboard_shortcut_out))
            if event['windows_key_code'] == cef.VK_ESCAPE:
                self.__source.stop()


class WebBrowserMediaSource(MediaSource):
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig, interface: MediaPlayerInterface,
                 executor: Executor):
        super().__init__(parent_logger, config, interface, executor)
        if not WebBrowserMediaSource.__logger:
            WebBrowserMediaSource.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                WebBrowserMediaSource.__logger.addHandler(handler)
            WebBrowserMediaSource.__logger.setLevel(parent_logger.level)
        # noinspection PyTypeChecker
        self.__web_browser_config: Dict[str, Any] = None
        self.__client_handler = WebBrowserClientHandler(parent_logger, self)
        settings = {
            # "product_version": "MyProduct/10.00",
            # "user_agent": "MyAgent/20.00 MyProduct/10.00",
        }
        cef.Initialize(settings=settings)
        # noinspection PyTypeChecker
        self._instance: cef.PyBrowser = None
        self.__playing: bool = False

    def get_image_path(self) -> str:
        return 'sources' + os.sep + 'images' + os.sep + 'web.jpg'

    def is_open(self) -> bool:
        return self._instance is not None

    def is_playing(self) -> bool:
        return self._instance is not None and self.__playing

    def get_name(self) -> str:
        return "BROWSER"

    def __load_web_config(self) -> None:
        path: str = self.get_config().get_root_path() + os.sep + 'web_browser_media_source.json'
        WebBrowserMediaSource.__logger.info('Loading configuration from: %s', path)
        if os.path.exists(path):
            with open(path, 'r') as fp:
                self.__web_browser_config = json.load(fp)
        else:
            with open(path, 'w') as fp:
                fp.write('{\n  "URL": "https://www.google.com"\n}')
            self.__web_browser_config = dict()

    def open(self) -> None:
        super().open()
        if not self.__web_browser_config:
            self.__load_web_config()
        window_info = cef.WindowInfo()
        window_info.SetAsChild(self._interface.get_view_handle(), [0, 0, self._interface.get_view_width(), self._interface.get_view_height()])
        self._instance = cef.CreateBrowserSync(window_info=window_info, url=self.__web_browser_config['URL'])
        self._instance.SetClientHandler(self.__client_handler)
        #self._executor.submit(cef.MessageLoop)
        cef.MessageLoop()

    def stop(self):
        super().stop()
        if self._instance:
            self._instance.CloseBrowser()
            cef.QuitMessageLoop()
            self._instance = None

    def get_volume(self) -> int:
        pass

    def set_volume(self, value: int) -> None:
        pass

    def play_next(self) -> None:
        pass

    def play_previous(self) -> None:
        pass
