# -*- coding: utf-*-
# Web browser Media definition
import json
import logging
import media_api
import os
import platform
import sys

from typing import Any, Dict
from media_api import MediaSource, MediaPlayerInterface, RemoteControlEvent
from media_player_config import MediaPlayerConfig
from id_threading_utils import Executor
from cefpython3 import cefpython as cef

sys.excepthook = cef.ExceptHook

if platform.system() in ("Linux", "Darwin"):
    WindowUtils = cef.WindowUtils()
    WindowUtils.InstallX11ErrorHandlers()

URL_KEY: str = "URL"
LANGUAGES_KEY: str = "accept_languages"
DEFAULT_URL: str = "https://www.google.com"
DEFAULT_LANGUAGES: str = "it-IT,fr-FR"


# noinspection PyUnusedLocal
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
        if event['type'] == cef.KEYEVENT_KEYUP:
            WebBrowserClientHandler.__logger.debug(event)
            if event['windows_key_code'] == cef.VK_ESCAPE:
                self.__source._interface.send_control_event(RemoteControlEvent(media_api.CODE_BACK))
            elif event['windows_key_code'] == cef.VK_ADD:
                self.__source._interface.send_control_event(RemoteControlEvent(media_api.CODE_VOL_UP))
            elif event['windows_key_code'] == cef.VK_SUBTRACT:
                self.__source._interface.send_control_event(RemoteControlEvent(media_api.CODE_VOL_DOWN))
            if event['modifiers'] == cef.EVENTFLAG_CONTROL_DOWN:
                if event['windows_key_code'] == cef.VK_Q:
                    self.__source._interface.send_control_event(RemoteControlEvent(media_api.CODE_POWER))
                elif event['windows_key_code'] == cef.VK_ADD:
                    self.__source._interface.send_control_event(RemoteControlEvent(media_api.CODE_CH_UP))
                elif event['windows_key_code'] == cef.VK_SUBTRACT:
                    self.__source._interface.send_control_event(RemoteControlEvent(media_api.CODE_CH_DOWN))


# noinspection PyUnusedLocal
class WebBrowserLifespanHandler:
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, source):
        if not WebBrowserLifespanHandler.__logger:
            WebBrowserLifespanHandler.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                WebBrowserLifespanHandler.__logger.addHandler(handler)
            WebBrowserLifespanHandler.__logger.setLevel(parent_logger.level)
        self.__source = source

    # noinspection PyPep8Naming
    def DoClose(self, browser) -> bool:
        WebBrowserLifespanHandler.__logger.debug('DoClose')
        return True


class WebBrowserFocusHandler:
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, source):
        if not WebBrowserFocusHandler.__logger:
            WebBrowserFocusHandler.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                WebBrowserFocusHandler.__logger.addHandler(handler)
            WebBrowserFocusHandler.__logger.setLevel(parent_logger.level)
        self.__source = source

    # noinspection PyPep8Naming
    def OnTakeFocus(self, browser, next_component) -> bool:
        WebBrowserFocusHandler.__logger.debug('OnTakeFocus')
        return False

    # noinspection PyPep8Naming
    def OnSetFocus(self, browser, source) -> bool:
        WebBrowserFocusHandler.__logger.debug('OnSetFocus')
        return True

    # noinspection PyPep8Naming
    def OnGotFocus(self, browser) -> None:
        WebBrowserFocusHandler.__logger.debug('OnGotFocus')


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
        self.__lifespan_handler = WebBrowserLifespanHandler(parent_logger, self)
        self.__focus_handler = WebBrowserFocusHandler(parent_logger, self)
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
        if not os.path.exists(path):
            self.__web_browser_config = dict()
            self.__web_browser_config[URL_KEY] = DEFAULT_URL
            self.__web_browser_config[LANGUAGES_KEY] = DEFAULT_LANGUAGES
            with open(path, 'w') as fp:
                json.dump(self.__web_browser_config, fp, indent=4, sort_keys=True)
        with open(path, 'r') as fp:
            self.__web_browser_config = json.load(fp)
        if URL_KEY not in self.__web_browser_config:
            self.__web_browser_config[URL_KEY] = DEFAULT_URL
        if LANGUAGES_KEY not in self.__web_browser_config:
            self.__web_browser_config[LANGUAGES_KEY] = DEFAULT_LANGUAGES

    def open(self) -> None:
        super().open()
        if not self.__web_browser_config:
            self.__load_web_config()
        app_settings = {
            "accept_language_list": self.__web_browser_config['accept_languages']
        }
        switches = {
            # GPU acceleration is not supported in OSR mode, so must disable
            # it using these Chromium switches (Issue #240 and #463)
            "disable-gpu": "",
            "disable-gpu-compositing": "",
            # Tweaking OSR performance by setting the same Chromium flags
            # as in upstream cefclient (Issue #240).
            "enable-begin-frame-scheduling": "",
            "disable-surfaces": "",  # This is required for PDF ext to work
        }
        browser_settings = {
            "accept_language_list": self.__web_browser_config['accept_languages'],
            "dom_paste_disabled": True,
            "javascript_close_windows_disallowed": True,
            "javascript_access_clipboard_disallowed": True,
            "plugins_disabled": True,
            "shrink_standalone_images_to_fit": True,
            "webgl_disabled": True
        }
        self._interface.set_grid_visible(False)
        cef.Initialize(settings=app_settings, switches=switches)
        window_info = cef.WindowInfo()
        window_info.SetAsChild(self._interface.get_view_handle(), [0, 0, self._interface.get_view_width(), self._interface.get_view_height()])
        self._instance = cef.CreateBrowserSync(window_info=window_info, url=self.__web_browser_config['URL'], settings=browser_settings)
        self._instance.SetClientHandler(self.__client_handler)
        self._instance.SetClientHandler(self.__lifespan_handler)
        self._instance.SetClientHandler(self.__focus_handler)
        if self._listener:
            self._listener.on_source_opened(self)
        cef.MessageLoop()

    def close(self):
        if self._instance:
            self._instance.CloseBrowser(True)
            self._instance = None
            cef.QuitMessageLoop()
        super().stop()
        if self._listener:
            self._listener.on_source_close(self)

    def get_volume(self) -> int:
        return 0

    def set_volume(self, value: int) -> None:
        pass

    def play_next(self) -> None:
        if self._instance and self._instance.CanGoForward():
            self._instance.GoForward()

    def play_previous(self) -> None:
        if self._instance and self._instance.CanGoBack():
            self._instance.GoBack()
