# -*- coding: utf-*-
# VLC Media API definition
import cv2
import datetime
import json
import logging
import os
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import requests
from typing import Any, Dict
from PIL import Image
from canvas_grid import CanvasGridRenderer
from media_api import MediaPlayerInterface, Media
from media_player_config import MediaPlayerConfig
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

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
os.environ["OPENCV_LOG_LEVEL"] = "WARN"


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
        self.__enabled: bool = True
        cv2.setLogLevel(0)

    def set_enabled(self, flag: bool) -> None:
        self.__enabled = flag

    def is_enabled(self) -> bool:
        return self.__enabled

    def render_image(self, value: Any) -> Image:
        if not isinstance(value, Media):
            return None
        media: Media = value
        if media.get_stream_url():
            # noinspection PyTypeChecker
            result: Image = None
            url: str = media.get_stream_url()
            if 'flavour=' in url:
                url = url.replace('flavour=hd', 'flavour=sd')
            if self.__enabled:
                colors: int = 0
                tries = 0
                while colors < _THUMBNAIL_MIN_COLORS and tries < _THUMBNAIL_TRIES:
                    tries = tries + 1
                    FreeboxMediaCellRenderer.__logger.info('Loading (try: %s) image of media from: %s', tries, url)
                    cap = cv2.VideoCapture(url)
                    # noinspection PyBroadException
                    try:
                        ret, frame = cap.read()
                        image: Image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        image_w, image_h = image.size
                        if image_w > 512 and image_h > 512:
                            image.thumbnail((512, 512), Image.ANTIALIAS)
                        by_color = {}
                        colors = 0
                        for pixel in image.getdata():
                            if pixel not in by_color:
                                by_color[pixel] = True
                                colors = colors + 1
                            if colors >= _THUMBNAIL_MIN_COLORS:
                                result = image
                                break
                        time.sleep(0.1)
                    except:  # catch all
                        time.sleep(0.2)
                        if tries >= _THUMBNAIL_TRIES:
                            FreeboxMediaCellRenderer.__logger.warning('Unexpected error: %s', sys.exc_info()[0])
                    finally:
                        if cap:
                            cap.release()
            if result is None:
                if media.get_image():
                    result = media.get_image()
                elif media.get_image_url():
                    FreeboxMediaCellRenderer.__logger.debug('Loading media image from: %s', media.get_image_url())
                    # noinspection PyTypeChecker
                    binary_response: requests.Response = None
                    # noinspection PyBroadException
                    try:
                        binary_response = requests.get(media.get_image_url(), stream=True)
                        media.set_image(Image.open(binary_response.raw))
                        result = media.get_image()
                    except:  # catch all
                        FreeboxMediaCellRenderer.__logger.error(traceback.format_exc())
                    finally:
                        if binary_response:
                            binary_response.close()
            else:
                url: str = _FREEBOX_CHANNEL_DESCRIPTION_PATTTERN % (media.get_stream_id(), str(int(time.time())))
                FreeboxMediaCellRenderer.__logger.debug('Loading media title from: %s', url)
                # noinspection PyBroadException
                try:
                    with urllib.request.urlopen(url) as json_response:
                        data = json.loads(json_response.read().decode(_UTF8))['result']
                        for k, v in data.items():
                            if 'title' in v:
                                media.set_title(v['title'])
                                if 'duration' in v:
                                    media.set_duration(v['duration'])
                                break
                except:  # catch all
                    FreeboxMediaCellRenderer.__logger.error(traceback.format_exc())
                    # noinspection PyTypeChecker
                    media.set_title(None)
                    # noinspection PyTypeChecker
                    media.set_duration(None)
            return result
        return None


class FreeboxMediaSource(VlcMediaSource):
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig, interface: MediaPlayerInterface):
        super().__init__(parent_logger, config, interface)
        if not FreeboxMediaSource.__logger:
            FreeboxMediaSource.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                FreeboxMediaSource.__logger.addHandler(handler)
            FreeboxMediaSource.__logger.setLevel(parent_logger.level)
        # noinspection PyTypeChecker
        self.__last_retrieval: datetime.datetime = None
        # noinspection PyTypeChecker
        self.__freebox_config: Dict[str, Any] = None
        self.__refresh_interface_delay: int = 30
        # Tasks
        # noinspection PyTypeChecker
        self.__refresh_interface_task: threading.Timer = None
        # noinspection PyTypeChecker
        self.__media_cell_renderer: FreeboxMediaCellRenderer = FreeboxMediaCellRenderer(parent_logger, config)

    def get_name(self) -> str:
        """
        Return the name
        :return: the name.
        """
        return "FREEBOX"

    def get_image_path(self) -> str:
        return 'sources' + os.sep + 'images' + os.sep + 'freebox.jpg'

    def refresh_interface(self) -> None:
        delay: int = self.__refresh_interface_delay
        if self.is_playing():
            delay = 60
        elif self._interface:
            self.__media_cell_renderer.set_enabled(True)
            self._interface.refresh()
        if self._interface and delay > 0:
            self.__refresh_interface_task = threading.Timer(delay, self.refresh_interface)
            self.__refresh_interface_task.start()

    def open(self) -> None:
        super().open()
        # noinspection PyTypeChecker
        self.__media_cell_renderer.set_enabled(False)
        self._interface.set_cell_renderer(self.__media_cell_renderer)
        if not self.__freebox_config:
            self.__load_freebox_config()
        if len(self._media_list) == 0:
            self.__build_media_list()
            self._media_list.sort(key=lambda v: v.get_channel())
        position: int = 0
        for media in self._media_list:
            self._interface.add_grid_cell(position=position, value=media, render=False)
            position = position + 1
        threading.Timer(5, self.refresh_interface).start()

    def close(self) -> None:
        self.__media_cell_renderer.set_enabled(False)
        if self.__refresh_interface_task:
            self.__refresh_interface_task.cancel()
            self.__refresh_interface_task = None
        super().close()

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
            self.__freebox_config['filters'] = list()
        FreeboxMediaSource.__logger.info(str(len(self.__freebox_config['filters'])) + ' filters loaded')

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
            FreeboxMediaSource.__logger.debug('Retrieving media list from: %s', _FREEBOX_STREAMS)
            media_list: dict = dict()
            with urllib.request.urlopen(_FREEBOX_CHANNELS) as response:
                data = json.loads(response.read().decode(_UTF8))['result']
                for k, v in data.items():
                    if 'name' not in v or v['name'] in self.__freebox_config['filters']:
                        continue
                    media: Media = Media(name=v['name'])
                    if 'logo_url' in v:
                        media.set_image_url(_HTTP_PREFIX + _FREEBOX_HOST + v['logo_url'])
                    media_list[media.get_name()] = media
            with urllib.request.urlopen(_FREEBOX_STREAMS) as response:
                for line in response.read().decode(_UTF8).splitlines():
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
                    elif name not in self.__freebox_config['filters']:
                        url = urllib.parse.urlparse(line.encode(_UTF8))
                        url_parameters = urllib.parse.parse_qs(url.query)
                        uuid = url_parameters[b'service'][0].decode(_UTF8)
                        flavour = None
                        if b'flavour' in url_parameters:
                            flavour = url_parameters[b'flavour'][0].decode(_UTF8)
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
