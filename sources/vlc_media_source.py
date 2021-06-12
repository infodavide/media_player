# -*- coding: utf-*-
# VLC Media definition
import logging
import os
import sys
import traceback
import vlc
import media_api

from abc import ABC
from media_player_config import MediaPlayerConfig
from media_api import RemoteControlEvent, MediaSource, MediaPlayerInterface, Media


class VlcMediaSource(MediaSource, ABC):
    logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig, interface: MediaPlayerInterface):
        super().__init__(parent_logger, config, interface)
        if not self.__class__.logger:
            self.__class__.logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                self.__class__.logger.addHandler(handler)
            self.__class__.logger.setLevel(parent_logger.level)
        # noinspection PyTypeChecker
        self._instance: vlc.Instance = None
        # noinspection PyTypeChecker
        self._player: vlc.MediaPlayer = None

    def get_image_path(self) -> str:
        return 'sources' + os.sep + 'images' + os.sep + 'vlc.jpg'

    def open(self) -> None:
        """
        Open the source.
        :return: None.
        """
        super().open()
        self.logger.debug("Starting VLC or using the existing one")
        try:
            if self._instance:
                self._instance.release()
            self._instance = vlc.Instance('--mouse-hide-timeout=0')
            if self._player:
                if self._player.is_playing():
                    self._player.stop()
                self._player.release()
            self._player = self._instance.media_player_new()
            self._player.set_fullscreen(True)
        except Exception as ex:
            self.logger.warning("An error occurred while starting VLC")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
            self.logger.error(ex)
            self._interface.display_error("An error occurred: " + repr(ex))

    def close(self) -> None:
        """
        Close the source.
        :return: None.
        """
        super().close()
        self.logger.debug("Closing VLC")
        try:
            if self._player:
                if self._player.is_playing():
                    self._player.stop()
                self._player.release()
                self._player = None
            if self._instance:
                self._instance.release()
                self._instance = None
            self.logger.info("VLC successfully closed")
        except Exception as ex:
            self.logger.warning("An error occurred while closing VLC")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
            self.logger.error(ex)
            self._interface.display_error("An error occurred: " + repr(ex))

    def is_open(self) -> bool:
        return self._instance is not None

    def is_playing(self) -> bool:
        return self._player is not None and self._player.is_playing()

    def on_stop(self) -> None:
        if self.is_open():
            self.close()

    def on_control_event(self, event: RemoteControlEvent) -> bytes:
        """
        Receive an event from remote control.
        :return: True if processed.
        """
        self.logger.debug('Event received: %s', event)
        if event.get_code() == media_api.CODE_BACK:
            if self._player and self._player.is_playing():
                self.logger.debug('Stopping player')
                self._player.stop()
                self._interface.set_playing(False)
        elif event.get_code() == media_api.CODE_CH and event.get_data():
            if self._player:
                if self._player.is_playing():
                    self.logger.debug('Stopping player')
                    self._player.stop()
                    self._interface.set_playing(False)
                # noinspection PyTypeChecker
                media: Media = None
                if isinstance(event.get_data(), Media):
                    media = event.get_data()
                elif isinstance(event.get_data(), str) and event.get_data().isnumeric():
                    channel: int = int(event.get_data())
                    for item in self._media_list:
                        if item.get_channel() == channel:
                            media = item
                if media:
                    self._media = media
                    vlc_media: vlc.Media = self._instance.media_new(media.get_stream_url())
                    self._interface.set_playing(True)
                    self.logger.info('Playing media: %s', media.get_name())
                    self._interface.display_notice('Playing media: ' + media.get_name())
                    self._player.set_xwindow(self._interface.get_window_id())
                    self._player.set_media(vlc_media)
                    self._player.play()
                    self.logger.info('Player stopped')
                else:
                    self.logger.warning('Media not available')
                    self._interface.display_warning('Media not available')
            else:
                self.logger.warning('Source not opened')
                self._interface.display_warning('Source not opened')
        else:
            self.logger.debug('Event ignored')
        return media_api.RESPONSE_ACK
