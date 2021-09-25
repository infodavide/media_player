# -*- coding: utf-*-
# Event dispatcher
import datetime
import io
import logging
import os
import sys
import threading
import traceback
from abc import ABC
from typing import Any, List

from PIL import Image

import media_api
from canvas_grid import CanvasGridRenderer
from id_classes_utils import subclasses_of, import_files_of_dir
from media_api import RemoteControlEvent, ControllerListener, MediaSource, InterfaceListener, MediaPlayerController, \
    Media
from media_player_config import MediaPlayerConfig
from media_player_interface import MediaPlayerInterface

available_sources: List[MediaSource] = list()
import_files_of_dir('sources')


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
            image_path: str = self.__config.get_root_path() + os.sep + source.get_image_path()
            MediaSourceCellRenderer.__logger.info('Loading image of source from: %s', image_path)
            with open(image_path, 'rb') as fp:
                return Image.open(io.BytesIO(fp.read()))
        return None


class EventDispatcher(ControllerListener, InterfaceListener):
    __logger: logging.Logger = None

    @staticmethod
    def is_pad_event(event: RemoteControlEvent) -> bool:
        return event.get_code() == media_api.CODE_OK or event.get_code() == media_api.CODE_LEFT or event.get_code() == media_api.CODE_RIGHT or event.get_code() == media_api.CODE_UP or event.get_code() == media_api.CODE_DOWN

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig, interface: MediaPlayerInterface,
                 controller: MediaPlayerController = None):
        """
        Initialize the event dispatcher.
        """
        super().__init__(config)
        if not EventDispatcher.__logger:
            EventDispatcher.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                EventDispatcher.__logger.addHandler(handler)
            EventDispatcher.__logger.setLevel(parent_logger.level)
        self.__interface: MediaPlayerInterface = interface
        self.__interface.set_listener(self)
        self.__controller: MediaPlayerController = controller
        # noinspection PyTypeChecker
        self.__pending_event: RemoteControlEvent = None
        # Tasks
        # noinspection PyTypeChecker
        self.__pending_event_task: threading.Timer = None
        # noinspection PyTypeChecker
        self.__source: MediaSource = None
        self.__source_cell_renderer: CanvasGridRenderer = MediaSourceCellRenderer(parent_logger, config)
        try:
            for subclass in subclasses_of(MediaSource):
                if 'Mock' in subclass.__name__ or ABC in subclass.__bases__:
                    continue
                EventDispatcher.__logger.info('Instantiating source: %s', subclass.__name__)
                obj: MediaSource = subclass(parent_logger, config, interface)
                available_sources.append(obj)
            self.__display_sources()
        except Exception as ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
            EventDispatcher.__logger.error(ex)
            self.__interface.display_error('An error occurred: ' + repr(ex))

    def __display_sources(self):
        self.__interface.set_cell_renderer(self.__source_cell_renderer)
        for source in available_sources:
            EventDispatcher.__logger.info('Using source: %s', source.get_name())
            self.__interface.add_grid_cell(value=source, render=True)

    def __del__(self):
        if self.__pending_event_task:
            self.__pending_event_task.cancel()
            self.__pending_event_task = None

    def get_controller(self) -> MediaPlayerController:
        return self.__controller

    def get_interface(self) -> MediaPlayerInterface:
        return self.__interface

    def set_controller(self, controller: MediaPlayerController) -> None:
        self.__controller = controller

    def on_validation(self, grid, value: Any) -> None:
        EventDispatcher.__logger.debug('Validation of: %s', value)
        if self.__interface:
            if isinstance(value, MediaSource):
                source: MediaSource = value
                if self.__source == source:
                    return
                if self.__source:
                    self.__source.close()
                self.__source = source
                self.__source.open()
            elif self.__source and isinstance(value, Media):
                media: Media = value
                self.__source.on_control_event(RemoteControlEvent(code=media_api.CODE_CH, data=media))

    def on_selection(self, grid, value: Any) -> None:
        EventDispatcher.__logger.debug('Selection of: %s', value)
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

    def on_stop(self) -> None:
        if self.__pending_event_task:
            self.__pending_event_task.cancel()
            self.__pending_event_task = None
        if self.__source:
            EventDispatcher.__logger.debug('Closing source: %s', self.__source.get_name())
            self.__source.close()
            self.__source = None
        if self.__interface:
            self.__interface.stop()
            self.__interface = None
        if self.__controller:
            EventDispatcher.__logger.debug('Stop event forwarded to controller')
            self.__controller.stop()

    def on_control_event(self, event: RemoteControlEvent) -> bytes:
        result: bytes = media_api.RESPONSE_ACK
        EventDispatcher.__logger.debug('Event received: %s', event)
        try:
            # Accumulate numeric values and set the new event with accumulated value as the pending one
            numeric_data: int = event.to_numeric()
            if event != self.__pending_event and numeric_data and numeric_data >= 0:
                EventDispatcher.__logger.debug('Accumulating numeric value described by the event')
                if self.__pending_event_task:
                    self.__pending_event_task.cancel()
                if self.__pending_event is None:
                    self.__pending_event = event
                else:
                    self.__pending_event.set_data(self.__pending_event.get_data() * 10 + numeric_data)
                self.__pending_event_task = threading.Timer(3, self.on_control_event, [self.__pending_event])
                self.__pending_event_task.start()
                return bytes()
            # Event is the accumulated (pending) one, it must be cleared
            if event == self.__pending_event:
                self.__pending_event = None
            EventDispatcher.__logger.debug('Processing received: %s', event)
            # Power or return from the main screen
            if event.get_code() == media_api.CODE_POWER or (not self.__source and event.get_code() == media_api.CODE_BACK):
                EventDispatcher.__logger.debug('Power event received')
                if self.__source:
                    self.__source.close()
                if self.__controller:
                    self.__controller.stop()
                if self.__interface:
                    self.__interface.stop()
            elif self.__interface and EventDispatcher.is_pad_event(event):
                EventDispatcher.__logger.debug('Pad event forwarded to the interface')
                result = self.__interface.on_control_event(event)
            # Go to source if no media is played
            elif event.get_code() == media_api.CODE_SOURCE or (self.__source and event.get_code() == media_api.CODE_BACK and not self.__source.is_playing()):
                EventDispatcher.__logger.debug('Source event received')
                self.__interface.set_cell_renderer(self.__source_cell_renderer)
                if self.__source:
                    EventDispatcher.__logger.debug('Closing source: %s', self.__source.get_name())
                    self.__source.close()
                    self.__source = None
                if event.get_code() == media_api.CODE_BACK:
                    self.__display_sources()
                else:
                    if numeric_data and 0 <= numeric_data < len(available_sources):
                        self.__source = available_sources[int(event.get_data())]
                        EventDispatcher.__logger.debug('Opening source: %s', self.__source.get_name())
                        if self.__interface:
                            self.__interface.display_notice('Using source: ' + self.__source.get_name())
                        self.__source.open()
                    else:
                        EventDispatcher.__logger.warning('Source: %s not found', event.get_data())
                        if self.__interface:
                            self.__interface.display_warning('Source: %s not found' % event.get_data())
            elif self.__source:
                EventDispatcher.__logger.debug('Event forwarded to the source: %s', self.__source.get_name())
                threading.Thread(target=self.__source.on_control_event, args=(event,)).start()
            else:
                EventDispatcher.__logger.debug('No source selected')
                if self.__interface:
                    self.__interface.display_warning('A source must be selected before sending commands.')
        except Exception as ex:
            EventDispatcher.__logger.warning('An error occurred while dispatching event: %s', event)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
            EventDispatcher.__logger.error(ex)
            if self.__interface:
                self.__interface.display_error('An error occurred: ' + repr(ex))
            return media_api.RESPONSE_NACK
        return result
