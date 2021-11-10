# -*- coding: utf-*-
# Event dispatcher
import datetime
import io
import logging
import media_api
import os
import pathlib
import platform
import pyautogui
import sys
import traceback

from abc import ABC
from typing import Any, List
from PIL import Image
from canvas_grid import CanvasGridRenderer
from id_classes_utils import subclasses_of, import_files_of_dir
from media_api import RemoteControlEvent, ControllerListener, MediaSource, MediaSourceListener, InterfaceListener, MediaPlayerController, Media
from media_player_config import MediaPlayerConfig
from media_player_interface import MediaPlayerInterface
from id_threading_utils import Executor

_STOPPING_EXECUTOR_MSG: str = 'Stopping executor'
_STOPPING_CONTROLLER_MSG: str = 'Stopping controller'
_STOPPING_INTERFACE_MSG: str = 'Stopping interface'
_CLOSING_SOURCE_MSG: str = 'Closing source: %s'
_NO_SOURCE_SELECTED_MSG: str = 'No source selected'
_SOURCE_NOT_FOUND_MSG: str = 'Source: %s not found'
_AN_ERROR_OCCURRED_MSG: str = 'An error occurred: %s'

available_sources: List[MediaSource] = list()
import_files_of_dir(str(pathlib.Path(__file__).parent) + os.sep + 'sources')


class MediaSourceCellRenderer(CanvasGridRenderer):
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig):
        super().__init__(parent_logger)
        if not MediaSourceCellRenderer.__logger:
            MediaSourceCellRenderer.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                MediaSourceCellRenderer.__logger.addHandler(handler)
            MediaSourceCellRenderer.__logger.setLevel(parent_logger.level)
        self.__config: MediaPlayerConfig = config

    def render_image(self, value: Any) -> Image:
        if not isinstance(value, MediaSource):
            return
        source: MediaSource = value
        if source.get_image_path():
            MediaSourceCellRenderer.__logger.debug('Rendering image a: %s', source.get_image_path())
            image_path: str = self.__config.get_root_path() + os.sep + source.get_image_path()
            with open(image_path, 'rb') as fp:
                return Image.open(io.BytesIO(fp.read()))
        return None


class ControlEventHandler(ControllerListener, InterfaceListener, MediaSourceListener):
    __logger: logging.Logger = None

    @staticmethod
    def is_pad_event(event: RemoteControlEvent) -> bool:
        return event.get_code() == media_api.CODE_OK or event.get_code() == media_api.CODE_LEFT or event.get_code() == media_api.CODE_RIGHT or event.get_code() == media_api.CODE_UP or event.get_code() == media_api.CODE_DOWN

    @staticmethod
    def is_raspberry_pi() -> bool:
        return platform.machine() in ('armv7l', 'armv6l')

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig, interface: MediaPlayerInterface, executor: Executor, controller: MediaPlayerController = None):
        """
        Initialize the event dispatcher.
        """
        super().__init__(config)
        if not ControlEventHandler.__logger:
            ControlEventHandler.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                ControlEventHandler.__logger.addHandler(handler)
            ControlEventHandler.__logger.setLevel(parent_logger.level)
        ControlEventHandler.__logger.debug('Platform: %s', platform.machine())
        self.__interface: MediaPlayerInterface = interface
        self.__interface.set_listener(self)
        self.__controller: MediaPlayerController = controller
        self.__executor: Executor = executor
        # noinspection PyTypeChecker
        self.__pending_event: RemoteControlEvent = None
        # noinspection PyTypeChecker
        self.__source: MediaSource = None
        self.__source_cell_renderer: CanvasGridRenderer = MediaSourceCellRenderer(parent_logger, config)
        try:
            for subclass in subclasses_of(MediaSource):
                if 'Mock' in subclass.__name__ or ABC in subclass.__bases__:
                    continue
                ControlEventHandler.__logger.info('Instantiating source: %s', subclass.__name__)
                obj: MediaSource = subclass(parent_logger, config, interface, self.__executor)
                obj.set_listener(self)
                available_sources.append(obj)
            available_sources.sort(key=lambda o: o.get_name())
            self.__display_sources()
        except Exception as ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
            ControlEventHandler.__logger.error(ex)
            self.__interface.display_error(_AN_ERROR_OCCURRED_MSG % repr(ex))

    def __display_sources(self):
        self.__interface.set_cell_renderer(self.__source_cell_renderer)
        self.__interface.set_grid_cells([])
        for source in available_sources:
            ControlEventHandler.__logger.info('Using source: %s', source.get_name())
            self.__interface.add_grid_cell(value=source, render=True)

    def get_controller(self) -> MediaPlayerController:
        return self.__controller

    def get_interface(self) -> MediaPlayerInterface:
        return self.__interface

    def set_controller(self, controller: MediaPlayerController) -> None:
        self.__controller = controller

    def on_grid_validation(self, grid, value: Any) -> None:
        ControlEventHandler.__logger.debug('Validation of: %s', value)
        if self.__interface:
            if isinstance(value, MediaSource):
                source: MediaSource = value
                if self.__source == source:
                    return
                self.__interface.set_grid_cells([])
                if self.__source:
                    self.__source.close()
                self.__source = source
                self.__source.open()
            elif self.__source and isinstance(value, Media):
                media: Media = value
                self.__source.play(media=media)

    def on_grid_selection(self, grid, value: Any) -> None:
        ControlEventHandler.__logger.debug('Selection of: %s', value)
        if self.__interface:
            if isinstance(value, MediaSource):
                source: MediaSource = value
                self.__interface.display_notice(source.get_name())
            elif isinstance(value, Media):
                media: Media = value
                text: str = media.get_name()
                if media.get_title():
                    text = text + ' - ' + media.get_title()
                if media.get_duration() and media.get_duration() > 0:
                    text = text + ' - ' + "{:0>8}".format(
                        str(datetime.timedelta(seconds=media.get_duration())))
                self.__interface.display_notice(text)

    def on_controller_stop(self) -> None:
        if self.__executor:
            ControlEventHandler.__logger.debug(_STOPPING_EXECUTOR_MSG)
            self.__executor.shutdown(wait=False)
            self.__executor = None
        if self.__source:
            ControlEventHandler.__logger.debug(_CLOSING_SOURCE_MSG, self.__source.get_name())
            self.__source.close()
            self.__source = None
        if self.__interface:
            ControlEventHandler.__logger.debug(_STOPPING_INTERFACE_MSG)
            self.__interface.stop()
            self.__interface = None

    def on_interface_stop(self) -> None:
        if self.__executor:
            ControlEventHandler.__logger.debug(_STOPPING_EXECUTOR_MSG)
            self.__executor.shutdown(wait=False)
            self.__executor = None
        if self.__source:
            ControlEventHandler.__logger.debug(_CLOSING_SOURCE_MSG, self.__source.get_name())
            self.__source.close()
            self.__source = None
        if self.__controller:
            ControlEventHandler.__logger.debug(_STOPPING_CONTROLLER_MSG)
            self.__controller.stop()
            self.__controller = None

    def on_source_opened(self, source: MediaSource, media: Media = None) -> None:
        ControlEventHandler.__logger.debug('Source opened: %s', source.get_name())
        if self.__interface:
            self.__interface.set_playing(False)
            if media:
                self.__interface.display_notice('Using media: ' + media.get_name())
            else:
                self.__interface.display_notice('Using source: ' + source.get_name())

    def on_source_close(self, source: MediaSource, media: Media = None) -> None:
        ControlEventHandler.__logger.debug('Source closed: %s', source.get_name())
        self.__source = None
        if self.__interface:
            self.__interface.set_playing(False)
            self.__interface.set_grid_visible(True)
            self.__display_sources()
            self.__interface.display_notice(_NO_SOURCE_SELECTED_MSG)

    def on_media_paused(self, source: MediaSource, media: Media) -> None:
        if self.__interface and media:
            self.__interface.display_notice(media.get_name() + ' paused')

    def on_media_played(self, source: MediaSource, media: Media) -> None:
        self.__interface.set_playing(True)
        if self.__interface and media:
            self.__interface.display_notice('Playing ' + media.get_name())

    def on_media_stopped(self, source: MediaSource, media: Media) -> None:
        if self.__interface and media:
            self.__interface.set_playing(False)
            self.__interface.set_grid_visible(True)
            self.__interface.display_notice(media.get_name() + ' stopped')

    def on_control_event(self, event: RemoteControlEvent) -> bytes:
        result: bytes = media_api.RESPONSE_ACK
        ControlEventHandler.__logger.debug('Event received: %s', event)
        try:
            # Accumulate numeric values and set the new event with accumulated value as the pending one
            numeric_data: int = event.to_numeric()
            if event != self.__pending_event and numeric_data and numeric_data >= 0:
                ControlEventHandler.__logger.debug('Accumulating numeric value described by the event')
                if self.__pending_event is None:
                    self.__pending_event = event
                    self.__pending_event.set_data(numeric_data)
                else:
                    self.__pending_event.set_data(numeric_data + self.__pending_event.get_data() * 10)
                self.__executor.schedule(3, self.on_control_event, self.__pending_event)
                return result
            # Event is the accumulated (pending) one, it must be cleared
            if event == self.__pending_event:
                self.__pending_event = None
            ControlEventHandler.__logger.debug('Processing received: %s', event)
            # Power or return from the main screen
            if not self.__source and event.get_code() == media_api.CODE_BACK:
                ControlEventHandler.__logger.debug(_NO_SOURCE_SELECTED_MSG)
            elif event.get_code() == media_api.CODE_POWER:
                if ControlEventHandler.is_raspberry_pi():
                    os.system("sudo shutdown now -fh")
                elif self.__controller:
                    self.__controller.stop()
            elif event.get_code() == media_api.CODE_OK:
                pyautogui.press('enter')
            elif event.get_code() == media_api.CODE_LEFT:
                pyautogui.press('left')
            elif event.get_code() == media_api.CODE_RIGHT:
                pyautogui.press('right')
            elif event.get_code() == media_api.CODE_UP:
                pyautogui.press('up')
            elif event.get_code() == media_api.CODE_DOWN:
                pyautogui.press('down')
            # Go to source if no media is played
            elif event.get_code() == media_api.CODE_SOURCE or (self.__source and event.get_code() == media_api.CODE_BACK and not self.__source.is_playing()):
                self.__interface.set_cell_renderer(self.__source_cell_renderer)
                if self.__source:
                    ControlEventHandler.__logger.debug(_CLOSING_SOURCE_MSG, self.__source.get_name())
                    self.__source.close()
                    self.__source = None
                if event.get_code() != media_api.CODE_BACK:
                    if numeric_data and 0 <= numeric_data < len(available_sources):
                        self.__source = available_sources[int(event.get_data())]
                        ControlEventHandler.__logger.debug('Opening source: %s', self.__source.get_name())
                        self.__source.open()
                    else:
                        ControlEventHandler.__logger.warning(_SOURCE_NOT_FOUND_MSG, event.get_data())
                        if self.__interface:
                            self.__interface.display_warning(_SOURCE_NOT_FOUND_MSG % event.get_data())
            elif self.__source:
                if event.get_code() == media_api.CODE_BACK or event.get_code() == media_api.CODE_STOP:
                    self.__source.stop()
                elif event.get_code() == media_api.CODE_CH and event.get_data():
                    self.__source.play(channel=numeric_data)
                elif event.get_code() == media_api.CODE_VOL and event.get_data():
                    self.__source.set_volume(numeric_data)
                elif event.get_code() == media_api.CODE_CH_UP or event.get_code() == media_api.CODE_NEXT:
                    self.__source.play_next()
                elif event.get_code() == media_api.CODE_CH_DOWN or event.get_code() == media_api.CODE_PREVIOUS:
                    self.__source.play_previous()
                elif event.get_code() == media_api.CODE_VOL_UP:
                    current_volume: int = self.__source.get_volume()
                    if current_volume < 100:
                        self.__source.set_volume(current_volume + 1)
                    self.__interface.display_notice('Volume: %s' % self.__source.get_volume())
                elif event.get_code() == media_api.CODE_VOL_DOWN:
                    current_volume: int = self.__source.get_volume()
                    if current_volume > 0:
                        self.__source.set_volume(current_volume - 1)
                    self.__interface.display_notice('Volume: %s' % self.__source.get_volume())
            else:
                ControlEventHandler.__logger.debug(_NO_SOURCE_SELECTED_MSG)
                if self.__interface:
                    self.__interface.display_warning('A source must be selected before sending commands.')
        except Exception as ex:
            ControlEventHandler.__logger.warning('An error occurred while dispatching event: %s', event)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
            ControlEventHandler.__logger.error(ex)
            if self.__interface:
                self.__interface.display_error(_AN_ERROR_OCCURRED_MSG % repr(ex))
            return media_api.RESPONSE_NACK
        return result
