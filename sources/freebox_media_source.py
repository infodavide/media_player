# -*- coding: utf-*-
# VLC Media API definition
import urllib

import cv2
import datetime
import json
import logging
import os
import time
import traceback
import requests
from typing import Any, Dict, List
from PIL import Image
from canvas_grid import CanvasGridRenderer
from media_api import MediaPlayerInterface, Media
from media_player_config import MediaPlayerConfig
from id_threading_utils import Executor
from vlc_media_source import VlcMediaSource

# URL to use:
# RTSP streams for thumbnails: http://mafreebox.freebox.fr/freeboxtv/playlist.m3u
# List of the channels in JSON: http://mafreebox.freebox.fr/api/v8/tv/channels
# Logo of the channel: http://mafreebox.freebox.fr/api/v8/tv/img/channels/logos68x60/<channel id>.png
#  Example: http://mafreebox.freebox.fr/api/v8/tv/img/channels/logos68x60/uuid-webtv-404.png
# Channel id is avaialble in the list of channels.
# Descriptions of the programs for a channel: http://mafreebox.freebox.fr/api/v3/tv/epg/by_channel/<channel id>/<epoch time>
#  Example: http://mafreebox.freebox.fr/api/v8/tv/epg/by_channel/uuid-webtv-201/1627010113
_HTTP_PREFIX: str = 'http://'
_FREEBOX_HOST: str = 'mafreebox.freebox.fr'
_FREEBOX_STREAMS: str = _HTTP_PREFIX + _FREEBOX_HOST + '/freeboxtv/playlist.m3u'
_FREEBOX_STREAM_PATTERN: str = 'rtsp://' + _FREEBOX_HOST + '/fbxtv_pub/stream?namespace=1&service=%s'
_FREEBOX_CHANNELS: str = _HTTP_PREFIX + _FREEBOX_HOST + '/api/v8/tv/channels'
_FREEBOX_CHANNEL_DESCRIPTION_PATTTERN: str = _HTTP_PREFIX + _FREEBOX_HOST + '/api/v8/tv/epg/by_channel/uuid-webtv-%s/%s'
_THUMBNAIL_MIN_COLORS: int = 15
_THUMBNAIL_TRIES: int = 3
_UTF8: str = 'utf8'
_IMAGE_URL_PROPERTY: str = 'image_url'
_NAME_KEY: str = 'name'
_LOGO_URL_KEY: str = 'logo_url'
_FILTERS_KEY: str = 'filters'
_DATE_KEY: str = 'date'
_RESULT_KEY: str = 'result'
_TITLE_KEY: str = 'title'
_DURATION_KEY: str = 'duration'
_PICTURE_KEY: str = 'picture'
_PICTURE_BIG_KEY: str = 'picture_big'
_FLAVOUR_PARAM: bytes = b'flavour'
_SERVICE_PARAM: bytes = b'service'

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"


class FreeboxMediaCellRenderer(CanvasGridRenderer):
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig):
        super().__init__(parent_logger)
        if not FreeboxMediaCellRenderer.__logger:
            FreeboxMediaCellRenderer.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                FreeboxMediaCellRenderer.__logger.addHandler(handler)
            FreeboxMediaCellRenderer.__logger.setLevel(parent_logger.level)
        self.__config: MediaPlayerConfig = config
        cv2.setLogLevel(0)

    def render_image(self, value: Any) -> Image:
        if not isinstance(value, Media):
            return None
        media: Media = value
        # noinspection PyTypeChecker
        result: Image = None
        # Loading media image if not already done
        if media.get_image() is None and _IMAGE_URL_PROPERTY in media.get_properties():
            url: str = media.get_properties()[_IMAGE_URL_PROPERTY]
            FreeboxMediaCellRenderer.__logger.debug('Loading media image for: %s from url: %s', media.get_name(), url)
            # noinspection PyBroadException
            try:
                with requests.get(url, stream=True, timeout=0.5) as binary_response:
                    media.set_image(Image.open(binary_response.raw))
            except:  # catch all
                FreeboxMediaCellRenderer.__logger.error(traceback.format_exc())
                # noinspection PyTypeChecker
                media.set_image(None)
        # Loading media title
        epoch_time: int = int(time.time())
        url: str = _FREEBOX_CHANNEL_DESCRIPTION_PATTTERN % (media.get_stream_id(), str(epoch_time))
        FreeboxMediaCellRenderer.__logger.debug('Loading media information for: %s from url: %s', media.get_name(), url)
        # noinspection PyBroadException
        try:
            with requests.get(url, stream=False, timeout=0.5) as json_response:
                results = list()
                for k, v in  json_response.json()[_RESULT_KEY].items():
                    if _DATE_KEY in v:
                        results.append(v)
                results.sort(key=lambda d: d[_DATE_KEY])
            # noinspection PyTypeChecker
            result: dict = None
            for v in results:
                if v[_DATE_KEY] <= epoch_time:
                    result = v
                else:
                    break
            if result and _TITLE_KEY in result:
                media.set_title(result[_TITLE_KEY])
                if _DURATION_KEY in result:
                    media.set_duration(result[_DURATION_KEY])
                if _PICTURE_BIG_KEY in result:
                    with requests.get(_HTTP_PREFIX + _FREEBOX_HOST + result[_PICTURE_BIG_KEY], stream=True, timeout=0.5) as binary_response:
                        result = Image.open(binary_response.raw)
                elif _PICTURE_KEY in result:
                    with requests.get(_HTTP_PREFIX + _FREEBOX_HOST + result[_PICTURE_KEY], stream=True, timeout=0.5) as binary_response:
                        result = Image.open(binary_response.raw)
        except:  # catch all
            FreeboxMediaCellRenderer.__logger.error(traceback.format_exc())
            # noinspection PyTypeChecker
            media.set_title(None)
            # noinspection PyTypeChecker
            media.set_duration(None)
        if result is None:
            result = media.get_image()
        return result


class FreeboxMediaSource(VlcMediaSource):
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig, interface: MediaPlayerInterface, executor: Executor):
        super().__init__(parent_logger, config, interface, executor)
        if not FreeboxMediaSource.__logger:
            FreeboxMediaSource.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                FreeboxMediaSource.__logger.addHandler(handler)
            FreeboxMediaSource.__logger.setLevel(parent_logger.level)
        # noinspection PyTypeChecker
        self.__last_retrieval: datetime.datetime = None
        # noinspection PyTypeChecker
        self.__freebox_config: Dict[str, Any] = None
        # noinspection PyTypeChecker
        self.__media_cell_renderer: FreeboxMediaCellRenderer = FreeboxMediaCellRenderer(parent_logger, config)
        self.__load_freebox_config()
        self.__build_media_list()
        self._media_list.sort(key=lambda v: v.get_channel())

    def get_name(self) -> str:
        """
        Return the name
        :return: the name.
        """
        return "FREEBOX"

    def get_image_path(self) -> str:
        return 'sources' + os.sep + 'images' + os.sep + 'freebox.jpg'

    def refresh_interface(self) -> None:
        if self._instance and self._interface and not self.is_playing():
            self._interface.refresh()
        if self._instance:
            self._executor.schedule(60, self.refresh_interface)

    def open(self) -> None:
        super().open()
        # noinspection PyTypeChecker
        self._interface.set_cell_renderer(self.__media_cell_renderer)
        position: int = 0
        for media in self._media_list:
            self._interface.add_grid_cell(position=position, value=media, render=False)
            position = position + 1
        self._executor.schedule(3, self.refresh_interface)

    def __load_freebox_config(self) -> None:
        path: str = self.get_config().get_root_path() + os.sep + 'freebox_media_source.json'
        FreeboxMediaSource.__logger.info('Loading configuration from: %s', path)
        if os.path.exists(path):
            with open(path, 'r') as fp:
                self.__freebox_config = json.load(fp)
        else:
            with open(path, 'w') as fp:
                fp.write('{\n}')
            self.__freebox_config = dict()
        if 'filters' not in self.__freebox_config:
            self.__freebox_config[_FILTERS_KEY] = list()
        FreeboxMediaSource.__logger.info(str(len(self.__freebox_config[_FILTERS_KEY])) + ' filters loaded')

    def __build_media_list(self) -> None:
        """
        Build the media list.
        :return: None.
        """
        now: datetime.datetime = datetime.datetime.now()
        # noinspection PyTypeChecker
        expiration: datetime.datetime = None
        if self.__last_retrieval:
            expiration = self.__last_retrieval + datetime.timedelta(minutes=5)
        if expiration is None or expiration < now:
            FreeboxMediaSource.__logger.debug('Retrieving media list from: %s', _FREEBOX_CHANNELS)
            media_list: dict = dict()
            with requests.get(_FREEBOX_CHANNELS, timeout=0.5) as response:
                data = response.json()[_RESULT_KEY]
            for k, v in data.items():
                if _NAME_KEY not in v or v[_NAME_KEY] in self.__freebox_config[_FILTERS_KEY]:
                    continue
                media: Media = Media(name=v[_NAME_KEY])
                if _LOGO_URL_KEY in v:
                    media.get_properties()[_IMAGE_URL_PROPERTY] = _HTTP_PREFIX + _FREEBOX_HOST + v[_LOGO_URL_KEY]
                media_list[media.get_name()] = media
            # noinspection PyTypeChecker
            lines: List[str] = None
            # noinspection PyTypeChecker
            name: str = None
            position: int = 0
            FreeboxMediaSource.__logger.debug('Retrieving streams list from: %s', _FREEBOX_STREAMS)
            with requests.get(_FREEBOX_STREAMS, timeout=0.5) as response:
                lines = response.text.splitlines()
            for line in lines:
                line = line.strip()
                if len(line) == 0 or line.startswith('#EXTM3U') or '&flavour=ld' in line:
                    continue
                if line.startswith('#EXTINF:'):
                    inf = line.split(' - ')
                    position = int(inf[0].split(',')[1])
                    name = inf[1]
                    if '(' in name:
                        name = name.split('(')[0]
                    name = name.strip()
                elif name not in self.__freebox_config[_FILTERS_KEY]:
                    url = urllib.parse.urlparse(line.encode(_UTF8))
                    url_parameters = urllib.parse.parse_qs(url.query)
                    uuid = url_parameters[_SERVICE_PARAM][0].decode(_UTF8)
                    flavour = None
                    if _FLAVOUR_PARAM in url_parameters:
                        flavour = url_parameters[_FLAVOUR_PARAM][0].decode(_UTF8)
                    if name in media_list:
                        media: Media = media_list[name]
                        media.set_channel(position)
                        if media.get_stream_id() is None:
                            FreeboxMediaSource.__logger.debug('Adding media to the list: %s', media)
                            if position >= len(self._media_list):
                                self._media_list.append(media)
                            else:
                                self._media_list.insert(position, media)
                        if flavour is None or media.get_stream_url() is None:
                            media.set_stream_url(line)
                            media.set_stream_id(uuid)
