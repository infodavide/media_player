# -*- coding: utf-*-
# VLC Media definition
import logging
import os
import sys
import traceback
from abc import ABC

import vlc

import media_api
from media_api import RemoteControlEvent, MediaSource, MediaPlayerInterface, Media
from media_player_config import MediaPlayerConfig


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

    def _play_media(self, media: Media = None, channel: int = -1):
        if channel >= 0:
            for item in self._media_list:
                if item.get_channel() == channel:
                    media = item
                    break
        if media:
            self._media = media
            vlc_media: vlc.Media = self._instance.media_new(media.get_stream_url())
            self._interface.set_playing(True)
            self.logger.info('Playing media: %s', media.get_name())
            self._interface.display_notice('Playing media: ' + media.get_name())
            self._player.set_xwindow(self._interface.get_window_id())
            self._player.set_media(vlc_media)
            self._player.set_video_title_display(0, 5000)
            self._player.play()
            self.logger.info('Playing')
        else:
            self.logger.warning('Media not available')
            self._interface.display_warning('Media not available')

    def on_control_event(self, event: RemoteControlEvent) -> bytes:
        """
        Receive an event from remote control.
        :return: True if processed.
        """
        self.logger.debug('Event received: %s', event)
        numeric_data: int = event.to_numeric()
        if event.get_code() == media_api.CODE_BACK or event.get_code() == media_api.CODE_STOP:
            if self._player and self._player.is_playing():
                self.logger.debug('Stopping player')
                self._player.stop()
                self._interface.set_playing(False)
        elif event.get_code() == media_api.CODE_VOL_UP:
            if self._player:
                current_volume: int = self._player.audio_get_volume()
                if current_volume < 100:
                    self._player.audio_set_mute(False)
                    self._player.audio_set_volume(current_volume + 1)
                self._interface.display_notice('Volume: %s' % self._player.audio_get_volume())
        elif event.get_code() == media_api.CODE_VOL_DOWN:
            if self._player:
                current_volume: int = self._player.audio_get_volume()
                if current_volume > 0:
                    self._player.audio_set_volume(current_volume - 1)
                if self._player.audio_get_volume() <= 0:
                    self._player.audio_set_mute(True)
                self._interface.display_notice('Volume: %s' % self._player.audio_get_volume())
        elif event.get_code() == media_api.CODE_CH_UP or event.get_code() == media_api.CODE_NEXT:
            if self._player:
                if self._media:
                    self._play_media(media=self._media, channel=self._media.get_channel() + 1)
                else:
                    self._play_media(channel=1)
            else:
                self.logger.warning('Source not opened')
                self._interface.display_warning('Source not opened')
        elif event.get_code() == media_api.CODE_CH_DOWN or event.get_code() == media_api.CODE_PREVIOUS:
            if self._player:
                if self._media:
                    self._play_media(media=self._media, channel=self._media.get_channel() - 1)
                else:
                    self._play_media(channel=1)
            else:
                self.logger.warning('Source not opened')
                self._interface.display_warning('Source not opened')
        elif event.get_code() == media_api.CODE_VOL and event.get_data():
            if self._player and numeric_data and numeric_data >= 0:
                self._player.audio_set_volume(numeric_data)
        elif event.get_code() == media_api.CODE_PLAY:
            if self._player:
                if self._player.is_playing():
                    self._player.pause()
                elif self._media:
                    self._player.play()
        elif event.get_code() == media_api.CODE_CH and event.get_data():
            if self._player:
                self._player.audio_set_mute(False)
                if isinstance(event.get_data(), Media):
                    self._play_media(media=event.get_data())
                elif numeric_data:
                    self._play_media(media=self._media, channel=numeric_data)
            else:
                self.logger.warning('Source not opened')
                self._interface.display_warning('Source not opened')
        else:
            self.logger.debug('Event ignored')
        return media_api.RESPONSE_ACK
