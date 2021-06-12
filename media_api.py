# -*- coding: utf-*-
# Media API definition
import atexit
import logging
import signal
from abc import ABC, abstractmethod
from typing import List, Any, Callable
from media_player_config import MediaPlayerConfig
from canvas_grid import CanvasGridRenderer
from PIL import Image

CODE_LEFT: int = 0x0A
CODE_RIGHT: int = 0x0B
CODE_UP: int = 0x0C
CODE_DOWN: int = 0x0D
CODE_BACK: int = 0x0E
CODE_LIST: int = 0x0F
CODE_OK: int = 0x10
CODE_INFORMATION: int = 0x11
CODE_PREVIOUS: int = 0x12
CODE_NEXT: int = 0x13
CODE_PLAY: int = 0x14
CODE_STOP: int = 0x15
CODE_MUTE: int = 0x16
CODE_VOL_UP: int = 0x18
CODE_VOL_DOWN: int = 0x17
CODE_CH_UP: int = 0x1A
CODE_CH_DOWN: int = 0x1B
CODE_SOURCE: int = 0x1D
CODE_POWER: int = 0x1E
CODE_VOL: int = 0x19
CODE_CH: int = 0x1C
CODE_SEARCH: int = 0xA0
CODE_TEXT: int = 0xA1
RESPONSE_ACK: bytes = bytes([0x06, 0x0A, 0x0D])
RESPONSE_QRY: bytes = bytes([0x05, 0x0A, 0x0D])
RESPONSE_NACK: bytes = bytes([0x15, 0x0A, 0x0D])
CONTROLLER_EOM: bytes = bytes([0x0A, 0x0D])

ImageLoader = Callable[[Any], type(List)]


class RemoteControlEvent(object):
    def __init__(self, code: int, data: Any = None):
        self.__code: int = code
        self.__data: Any = data

    def get_code(self) -> int:
        return self.__code

    def get_data(self) -> Any:
        return self.__data

    def set_code(self, code: int) -> None:
        self.__code = code

    def set_data(self, value: Any) -> None:
        self.__data = value

    def __str__(self):
        return super().__str__() + ',' + str(self.__code) + ':' + str(self.__data)


class Media(object):
    def __init__(self, stream_id: str = None, channel: int = -1, stream_url: str = None, image_url: str = None, image: Image = None, name: str = None, title: str = None):
        self.__channel: int = channel
        self.__stream_id: str = stream_id
        self.__stream_url: str = stream_url
        self.__name: str = name
        self.__title: str = title
        self.__duration: int = 0
        self.__image: Image = image
        self.__image_url: str = image_url

    def get_channel(self) -> int:
        return self.__channel

    def get_stream_id(self) -> str:
        return self.__stream_id

    def get_image(self) -> Image:
        return self.__image

    def get_image_url(self) -> str:
        return self.__image_url

    def get_stream_url(self) -> str:
        return self.__stream_url

    def get_name(self) -> str:
        return self.__name

    def get_title(self) -> str:
        return self.__title

    def get_duration(self) -> int:
        return self.__duration

    def set_stream_id(self, value: str) -> None:
        self.__stream_id = value

    def set_image(self, value: Image) -> None:
        self.__image = value

    def set_image_url(self, value: str) -> None:
        self.__image_url = value

    def set_channel(self, value: int) -> None:
        self.__channel = value

    def set_stream_url(self, value: str) -> None:
        self.__stream_url = value

    def set_name(self, value: str) -> None:
        self.__name = value

    def set_title(self, value: str) -> None:
        self.__title = value

    def set_duration(self, value: int) -> None:
        self.__duration = value

    def __str__(self):
        result: list = list()
        result.append(super().__str__())
        if self.__name:
            result.append(self.__name)
        if self.__channel and self.__channel >= 0:
            result.append(str(self.__channel))
        if self.__title:
            result.append(self.__title)
        if self.__stream_url:
            result.append(self.__stream_url)
        return ','.join(result)


MediaList = List[Media]


class ControllerListener(ABC):
    @abstractmethod
    def on_stop(self) -> None:
        """
        Listener interface used to dispatch stop event.
        """
        pass

    @abstractmethod
    def on_control_event(self, event: RemoteControlEvent) -> bytes:
        """
        Listener interface used to dispatch events.
        """
        pass


class MediaPlayerController(ABC):
    def __init__(self, config: MediaPlayerConfig, listener: ControllerListener):
        """
        Initialize the controller.
        :param config: the configuration object
        :param listener: the listener
        """
        self._config: MediaPlayerConfig = config
        self._listener: ControllerListener = listener

    def get_config(self) -> MediaPlayerConfig:
        return self._config

    def get_listener(self) -> ControllerListener:
        return self._listener

    @abstractmethod
    def is_running(self) -> bool:
        """
        Check if running.
        :return: True if running
        """
        pass

    @abstractmethod
    def start(self) -> None:
        """
        Start the controller.
        :return:
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
        Stop the controller.
        :return:
        """
        pass

    @abstractmethod
    def restart(self):
        """
        Stop and start the controller.
        :return:
        """
        pass


class InterfaceListener(ABC):
    def __init__(self, config: MediaPlayerConfig):
        """
        Initialize the listener.
        """
        super().__init__()
        self._config: MediaPlayerConfig = config

    def get_config(self) -> MediaPlayerConfig:
        return self._config

    @abstractmethod
    def on_validation(self, source, value: Any) -> None:
        """
        Invoked when cell has been validated or chosen on the interface
        :param source: the source component
        :param value: the value
        """
        pass

    @abstractmethod
    def on_selection(self, source, value: Any) -> None:
        """
        Invoked when cell has been selected on the interface
        :param source: the source component
        :param value: the value
        """
        pass

    @abstractmethod
    def on_stop(self) -> None:
        """
        Listener interface used to dispatch stop event.
        """
        pass


class MediaPlayerInterface(ControllerListener):
    def __init__(self, config: MediaPlayerConfig):
        self._config: MediaPlayerConfig = config
        # noinspection PyTypeChecker
        self._listener: InterfaceListener = None
        # Hooks
        atexit.register(self.stop)
        signal.signal(signal.SIGINT, self.stop)

    def get_config(self) -> MediaPlayerConfig:
        """
        Returns the configuration
        :return: the configuration
        """
        return self._config

    def get_listener(self) -> InterfaceListener:
        """
        Returns the listener
        :return: the listener
        """
        return self._listener

    def set_listener(self, value: InterfaceListener) -> None:
        """
        Sets the listener
        :param value: the listener
        """
        self._listener = value

    @abstractmethod
    def get_cell_renderer(self) -> CanvasGridRenderer:
        """
        Returns the cell renderer
        :return: the renderer
        """
        pass

    @abstractmethod
    def set_cell_renderer(self, value: CanvasGridRenderer) -> None:
        """
        Sets the cell renderer
        :param value: the renderer
        """
        pass

    @abstractmethod
    def get_window_id(self) -> int:
        """
        Return the main window of the interface.
        """
        pass

    @abstractmethod
    def get_x(self) -> int:
        """
        Return the horizontal position.
        """
        pass

    @abstractmethod
    def get_y(self) -> int:
        """
        Return the vertical position.
        """
        pass

    @abstractmethod
    def get_width(self) -> int:
        """
        Return the width.
        """
        pass

    @abstractmethod
    def get_height(self) -> int:
        """
        Return the height.
        """
        pass

    @abstractmethod
    def set_playing(self, flag: bool) -> None:
        """
        Set the interface in playing mode or not.
        """
        pass

    @abstractmethod
    def toggle_full_screen(self) -> None:
        """
        Toggle the interface in full screen mode.
        """
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """
        Check if running.
        :return: True if running
        """
        pass

    @abstractmethod
    def start(self) -> None:
        """
        Start the interface.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
        Stop the interface.
        """
        pass

    @abstractmethod
    def restart(self) -> None:
        """
        Stop and start the interface.
        :return:
        """
        pass

    @abstractmethod
    def refresh(self) -> None:
        """
        Refresh the interface.
        :return:
        """
        pass

    @abstractmethod
    def display_notice(self, text: str) -> None:
        """
        Display a notice.
        :return:
        """
        pass

    @abstractmethod
    def display_warning(self, text: str) -> None:
        """
        Display a notice.
        :return:
        """
        pass

    @abstractmethod
    def display_error(self, text: str) -> None:
        """
        Display a notice.
        :return:
        """
        pass

    @abstractmethod
    def set_grid_cells(self, values: List) -> int:
        """
        Sets and display a grid using the given sources or media list
        :param values: the sources or media list to display
        :return: the number of visible cells
        """
        pass

    @abstractmethod
    def add_grid_cell(self, value: Any, position: int = -1, render: bool = True) -> int:
        """
        Add a new source or media to the displayed grid
        :param value: the source or media to add to the grid
        :param position: the position or -1 to append source or media on the grid
        :param render: true to render the cell and update the grid
        :return: the position on the grid
        """
        pass


class MediaSource(ControllerListener):
    logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig, interface: MediaPlayerInterface):
        """
        Set the logger and configuration.
        :param parent_logger: the logger
        :param config: the configuration
        """
        if not self.__class__.logger:
            self.__class__.logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                self.__class__.logger.addHandler(handler)
            self.__class__.logger.setLevel(parent_logger.level)
        self.__class__.logger.info('Initializing %s', self.__class__.__name__)
        self._config: MediaPlayerConfig = config
        self._interface: MediaPlayerInterface = interface
        # noinspection PyTypeChecker
        self._media_list: MediaList = list()
        # noinspection PyTypeChecker
        self._media: Media = None

    def get_interface(self) -> MediaPlayerInterface:
        return self._interface

    def get_media(self) -> Media:
        return self._media

    def get_media_list(self) -> MediaList:
        return self._media_list

    def get_config(self) -> MediaPlayerConfig:
        return self._config

    def play(self, media: Media) -> None:
        """
        Play the media.
        :return: None.
        """
        self._media = media
        self._interface.set_playing(True)

    def stop(self):
        """
        Stop playing the media.
        :return: None.
        """
        self._media = None
        self._interface.set_playing(False)

    def close(self) -> None:
        """
        Close the API.
        :return: None.
        """
        if self.is_playing():
            self.stop()

    def open(self) -> None:
        """
        Open the API.
        :return: None.
        """
        self._media = None
        self._interface.set_playing(False)

    @abstractmethod
    def is_open(self) -> bool:
        """
        Return true if opened
        :return: the boolean.
        """
        pass

    @abstractmethod
    def is_playing(self) -> bool:
        """
        Return true if playing
        :return: the boolean.
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Return the name
        :return: the name.
        """
        pass

    @abstractmethod
    def get_image_path(self) -> str:
        """
        Return the image
        :return: the path to the image.
        """
        pass

    def __str__(self):
        return super().__str__() + ',' + self.get_name() + ' (' + str(self.is_playing()) + ')'
