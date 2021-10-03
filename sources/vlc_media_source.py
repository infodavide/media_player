# -*- coding: utf-*-
# VLC Media definition
import logging
import os
import sys
import traceback
from abc import ABC

import vlc

import media_api
from media_api import MediaSource, MediaPlayerInterface, Media
from media_player_config import MediaPlayerConfig
from id_threading_utils import Executor


class VlcMediaSource(MediaSource, ABC):
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig, interface: MediaPlayerInterface, executor: Executor):
        super().__init__(parent_logger, config, interface, executor)
        if not VlcMediaSource.__logger:
            VlcMediaSource.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                VlcMediaSource.__logger.addHandler(handler)
            VlcMediaSource.__logger.setLevel(parent_logger.level)
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
        VlcMediaSource.__logger.debug("Starting VLC or using the existing one")
        try:
            if self._instance:
                self._instance.release()
            self._instance = vlc.Instance('--mouse-hide-timeout=0')
            if not self._player:
                self._player = self._instance.media_player_new()
            self._player.set_fullscreen(True)
        except Exception as ex:
            VlcMediaSource.__logger.warning("An error occurred while starting VLC")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
            VlcMediaSource.__logger.error(ex)
            self._interface.display_error("An error occurred: " + repr(ex))

    def close(self) -> None:
        """
        Close the source.
        :return: None.
        """
        super().close()
        VlcMediaSource.__logger.debug("Closing VLC")
        try:
            if self._player:
                if self._player.is_playing():
                    self._player.stop()
                self._player.release()
                self._player = None
            if self._instance:
                self._instance.release()
                self._instance = None
            VlcMediaSource.__logger.info("VLC successfully closed")
        except Exception as ex:
            VlcMediaSource.__logger.warning("An error occurred while closing VLC")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
            VlcMediaSource.__logger.error(ex)
            self._interface.display_error("An error occurred: " + repr(ex))

    def is_open(self) -> bool:
        return self._instance is not None

    def is_playing(self) -> bool:
        return self._player is not None and self._player.is_playing()

    def stop(self):
        if self._player and self._player.is_playing():
            self._player.stop()
            self._media = None
        super().stop()

    def play_media(self, media: Media = None, channel: int = -1) -> None:
        if self._media:
            if self._player.is_playing():
                self._player.pause()
            elif self._media:
                self._player.play()
        if channel >= 0:
            for item in self._media_list:
                if item.get_channel() == channel:
                    media = item
                    break
        if media:
            self._media = media
            vlc_media: vlc.Media = self._instance.media_new(media.get_stream_url())
            vlc_media.set_meta(0, media.get_name())
            self._interface.set_playing(True)
            VlcMediaSource.__logger.info('Playing media: %s', media.get_name())
            self._interface.display_notice('Playing media: ' + media.get_name())
            self._player.set_xwindow(self._interface.get_view_handle())
            self._player.set_media(vlc_media)
            self._player.set_video_title_display(0, 5000)
            self._player.play()
            VlcMediaSource.__logger.info('Playing')
        else:
            VlcMediaSource.__logger.warning(media_api.MEDIA_NOT_AVAILABLE)
            self._interface.display_warning(media_api.MEDIA_NOT_AVAILABLE)

    def get_volume(self) -> int:
        if self._player:
            return self._player.audio_get_volume()
        return 0

    def set_volume(self, value: int) -> None:
        if self._player:
            return self._player.audio_set_volume(value)

    def play_next(self) -> None:
        if self._player:
            if self._media:
                self.play_media(media=self._media, channel=self._media.get_channel() + 1)
            else:
                self.play_media(channel=1)
        else:
            VlcMediaSource.__logger.warning(media_api.SOURCE_NOT_OPENED)

    def play_previous(self) -> None:
        if self._player:
            if self._media:
                self.play_media(media=self._media, channel=self._media.get_channel() - 1)
            else:
                self.play_media(channel=1)
        else:
            VlcMediaSource.__logger.warning(media_api.SOURCE_NOT_OPENED)