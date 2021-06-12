# -*- coding: utf-*-
# Media player screen
import io
import logging
import media_api
import os
import pyautogui
import screeninfo
import sys
import threading
import time
import tkinter as tk
import traceback

from typing import Any, List
from media_player_config import MediaPlayerConfig
from media_api import RemoteControlEvent, MediaPlayerInterface, Media, MediaSource, ControllerListener
from canvas_grid import CanvasGrid, CanvasGridListener, CanvasGridCell, CanvasGridRenderer
from id_tk import TkClock
from PIL import Image, ImageTk


_FULLSCREEN: str = 'fullscreen'


class MediaPlayerInterfaceImpl(MediaPlayerInterface, CanvasGridListener):
    logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig):
        """
        Initialize the media player interface.
        :param parent_logger: the main logger
        :param config: the configuration object
        """
        super().__init__(config)
        if not MediaPlayerInterfaceImpl.logger:
            MediaPlayerInterfaceImpl.logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                MediaPlayerInterfaceImpl.logger.addHandler(handler)
            MediaPlayerInterfaceImpl.logger.setLevel(parent_logger.level)
        MediaPlayerInterfaceImpl.logger.info('Initializing %s', self.__class__.__name__)
        # Status flags
        self.__active: bool = False
        self.__playing: bool = False
        # Locks
        self.__lock: threading.RLock = threading.RLock()
        self.__start_lock: threading.RLock = threading.RLock()
        self.__stop_lock: threading.RLock = threading.RLock()
        # Tasks
        # noinspection PyTypeChecker
        self.__cleanup_top_task: threading.Timer = None
        # noinspection PyUnresolvedReferences
        self.__log_file_path: str = self._config.get_temp_dir() + os.sep + 'media_player.log'
        # noinspection PyTypeChecker
        self.__center_text_id: Any = None
        # noinspection PyTypeChecker
        self.__center_image_id: Any = None
        self.__full_screen_state: bool = True
        # noinspection PyTypeChecker
        self.__cell_type: type = None
        # Use the primary monitor
        monitor = screeninfo.get_monitors()[0]
        self.__window: tk.Tk = tk.Tk()
        self.__window.geometry('%dx%d' % (monitor.width, (monitor.height - 1)))
        self.__window.geometry('+' + str(monitor.x) + '+' + str(monitor.y))
        self.__window.title("Media player")
        self.__window['background'] = 'black'
        self.__window.bind('<F11>', self.toggle_full_screen)
        self.__window.bind('<Control-q>', self.stop)
        self.__window.bind('<Escape>', lambda e: self._on_key(RemoteControlEvent(media_api.CODE_BACK), e))
        self.__window.bind('<KP_Add>', lambda e: self._on_key(RemoteControlEvent(media_api.CODE_VOL_UP), e))
        self.__window.bind('<KP_Subtract>', lambda e: self._on_key(RemoteControlEvent(media_api.CODE_VOL_DOWN), e))
        self.__window.bind('<Control-KP_Add>', lambda e: self._on_key(RemoteControlEvent(media_api.CODE_CH_UP), e))
        self.__window.bind('<Control-KP_Subtract>', lambda e: self._on_key(RemoteControlEvent(media_api.CODE_CH_DOWN), e))
        for k in range(10):
            v: str = str(k)
            self.__window.bind('<KP_%s>' % v, lambda e, data=v: self._on_key(RemoteControlEvent(code=media_api.CODE_VOL, data=data), e))
            self.__window.bind('<Control-KP_%s>' % v, lambda e, data=v: self._on_key(RemoteControlEvent(code=media_api.CODE_CH, data=data), e))
        self.__window.attributes('-topmost', True)
        self.__window.attributes('-' + _FULLSCREEN, self.__full_screen_state)
        self.__window.minsize(1027, 768)
        w, h = self.__window.winfo_screenwidth(), self.__window.winfo_screenheight()
        MediaPlayerInterfaceImpl.logger.info('Screen size: %sx%s', w, h)
        self.__top_lbl = tk.Label(self.__window, text="Ready", bg="black", fg="white")
        self.__top_lbl.config(font=("Courier", 22))
        self.__top_lbl.pack(fill=tk.X, ipadx=10, padx=10, side=tk.TOP)
        self.__center_cnv = tk.Canvas(self.__window, bg="black", height=h - 110, width=w, borderwidth=0, highlightthickness=0)
        self.__center_cnv.pack(fill=tk.X, expand=tk.TRUE)
        self.__bottom_lbl = tk.Label(self.__window, text="Ready\n\n", bg="black", fg="orange", justify=tk.LEFT)
        self.__bottom_lbl.config(font=("Courier", 16))
        self.__bottom_lbl.pack(ipadx=5, padx=5, anchor=tk.S, side=tk.LEFT)
        self.__clock = TkClock(self.__window)
        self.__clock.config(font=("Courier", 16), bg="black", fg="orange")
        self.__clock.pack(ipadx=5, padx=5)
        with open(self._config.get_root_path() + os.sep + 'images' + os.sep + 'background.jpg', 'rb') as fp:
            image: Image = Image.open(io.BytesIO(fp.read()))
        image = image.resize((self.__center_cnv.winfo_width(), self.__center_cnv.winfo_height()), Image.ANTIALIAS)
        self.__center_image_id = self.__center_cnv.create_image(0, 0, image=ImageTk.PhotoImage(image), anchor=tk.NW)
        self.__window.update()
        self.__cnv_grid = CanvasGrid(MediaPlayerInterfaceImpl.logger, self.__window, self.__center_cnv)
        self.__cnv_grid.set_listener(self)
        MediaPlayerInterfaceImpl.logger.info('Media player interface configured')

    def _on_key(self, control_event: RemoteControlEvent, event: Any) -> None:
        if control_event and isinstance(self._listener, ControllerListener):
            MediaPlayerInterfaceImpl.logger.debug('Forwarding event to listener: %s', control_event)
            listener: ControllerListener = self._listener
            listener.on_control_event(control_event)

    def get_window_id(self) -> int:
        return self.__window.winfo_id()

    def get_x(self) -> int:
        if self.__window:
            return self.__window.winfo_x()
        return 0

    def get_y(self) -> int:
        if self.__window:
            return self.__window.winfo_y()
        return 0

    def get_width(self) -> int:
        if self.__window:
            return self.__window.winfo_width()
        return 0

    def get_height(self) -> int:
        if self.__window:
            return self.__window.winfo_height()
        return 0

    def get_cell_renderer(self) -> CanvasGridRenderer:
        return self.__cnv_grid.get_renderer()

    def set_cell_renderer(self, value: CanvasGridRenderer) -> None:
        self.__cnv_grid.set_renderer(value)

    def is_running(self) -> bool:
        return self.__active

    def start(self) -> None:
        """
        Start the threads.
        :return:
        """
        with self.__lock:
            if self.__active:
                return
        with self.__start_lock:
            MediaPlayerInterfaceImpl.logger.debug('Starting...')
            self.__active = True
            MediaPlayerInterfaceImpl.logger.info('Opening window...')
            # noinspection PyBroadException
            try:
                MediaPlayerInterfaceImpl.logger.info('Window opened')
                self.__top_lbl.place(rely=0.0, relx=1.0, x=0, y=0, anchor=tk.NE)
                self.__clock.place(rely=1.0, relx=1.0, x=0, y=0, anchor=tk.SE)
                self.__window.mainloop()
            except:  # catch all
                MediaPlayerInterfaceImpl.logger.error(traceback.format_exc())
            finally:
                MediaPlayerInterfaceImpl.logger.info('Stopped')
                if self.__window:
                    self.__window.destroy()
                self.__window = None
                self.__active = False
                if self._listener:
                    self._listener.on_stop()

    # noinspection PyUnusedLocal
    def stop(self, event: Any = None) -> None:
        """
        Stop the threads.
        :return:
        """
        with self.__lock:
            if not self.__active:
                return
        with self.__stop_lock:
            MediaPlayerInterfaceImpl.logger.info('Stopping...')
            self.__active = False
            try:
                if self.__window:
                    self.__window.quit()
            except Exception as ex:
                self.logger.error('Cannot stop interface: %s' % ex)
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
                self.logger.error(ex)

    def restart(self):
        self.stop()
        time.sleep(1)
        self.start()

    # noinspection PyUnusedLocal
    def toggle_full_screen(self, event: Any = None):
        self.logger.debug('Entering %s mode', _FULLSCREEN)
        self.__full_screen_state = not self.__full_screen_state
        self.__window.attributes('-' + _FULLSCREEN, self.__full_screen_state)

    # noinspection PyUnusedLocal
    def quit_full_screen(self, event: Any = None):
        self.logger.debug('Exiting %s mode', _FULLSCREEN)
        self.__full_screen_state = False
        self.__window.attributes('-' + _FULLSCREEN, self.__full_screen_state)

    def set_playing(self, flag: bool):
        self.__playing = flag
        self.logger.debug('Setting playing mode: %s', flag)

    def refresh(self) -> None:
        if not self.__playing:
            self.__cnv_grid.redraw()

    def __clear_text_at_top(self):
        MediaPlayerInterfaceImpl.logger.debug('Clearing text at top')
        self.__top_lbl['text'] = ''
        self.__cleanup_top_task = None

    def __clear_text_at_center(self):
        MediaPlayerInterfaceImpl.logger.debug('Clearing text at center')
        if self.__center_text_id:
            self.__center_cnv.delete(self.__center_text_id)

    def __display_at_top(self, text: str = None, color: str = None):
        if self.__cleanup_top_task and self.__cleanup_top_task.is_alive():
            self.__cleanup_top_task.cancel()
        if not self.__top_lbl:
            return
        if text:
            MediaPlayerInterfaceImpl.logger.debug('Displaying text at top: %s', text)
            self.__top_lbl['text'] = text
            self.__cleanup_top_task = threading.Timer(3, self.__clear_text_at_top)
            self.__cleanup_top_task.start()
        else:
            MediaPlayerInterfaceImpl.logger.debug('Displaying empty text at top')
            self.__top_lbl['text'] = ''
        if color:
            self.__top_lbl.configure(foreground=color)

    def __display_at_bottom(self, text: str = None, color: str = None):
        if not self.__bottom_lbl:
            return
        if text:
            MediaPlayerInterfaceImpl.logger.debug('Displaying text at bottom: %s', text)
            while text.count('\n') < 2:
                text = text + '\n'
            self.__bottom_lbl['text'] = text
        else:
            MediaPlayerInterfaceImpl.logger.debug('Displaying empty text at bottom')
            self.__bottom_lbl['text'] = '\n\n'
        if color:
            self.__bottom_lbl.configure(foreground=color)

    def __display_at_center(self, text: str = None, color: str = None):
        self.__clear_text_at_center()
        if not self.__center_text_id:
            return
        if text:
            MediaPlayerInterfaceImpl.logger.debug('Displaying text at center: %s', text)
            if color:
                self.__center_text_id = self.__center_cnv.create_text(0, 0, font="Courier 24 bold", text=text, tag='text', anchor=tk.NW, fill=color)
            else:
                self.__center_text_id = self.__center_cnv.create_text(0, 0, font="Courier 24 bold", text=text, tag='text', anchor=tk.NW, fill='white')
            text_coordinates = self.__center_cnv.bbox(self.__center_text_id)
            self.__center_cnv.move(self.__center_text_id, (self.__center_cnv.winfo_width() / 2) - ((text_coordinates[2] - text_coordinates[0]) / 2), 50)
        else:
            MediaPlayerInterfaceImpl.logger.debug('Displaying empty text at center')
            self.__clear_text_at_center()

    def display_notice(self, text: str) -> None:
        self.__display_at_bottom(text, 'white')

    def display_warning(self, text: str) -> None:
        self.__display_at_bottom(text, 'yellow')

    def display_error(self, text: str) -> None:
        self.__display_at_bottom(text, 'red')

    def on_cell_validation(self, grid, cell: CanvasGridCell) -> None:
        if self._listener:
            self._listener.on_validation(grid, cell.get_value())

    # noinspection PyUnusedLocal
    def on_cell_selection(self, grid, previous: CanvasGridCell, cell: CanvasGridCell) -> None:
        if self._listener:
            self._listener.on_selection(grid, cell.get_value())

    def set_grid_cells(self, values: List) -> int:
        self.__cnv_grid.clear()
        for value in values:
            self.add_grid_cell(value)
        return self.__cnv_grid.get_rows() * self.__cnv_grid.get_columns()

    def add_grid_cell(self, value: Any, position: int = -1, render: bool = True) -> int:
        if self.__cell_type != type(value):
            self.__cnv_grid.clear()
        self.__cell_type = type(value)
        if isinstance(value, MediaSource):
            source: MediaSource = value
            self.__cnv_grid.add_cell(position=position, label=source.get_name(), value=source)
            return position
        if isinstance(value, Media):
            media: Media = value
            self.__cnv_grid.add_cell(position=position, label=media.get_name(), value=media)
            return position
        MediaPlayerInterfaceImpl.logger.warning('Type of value not handled: %s', self.__cell_type)
        return -1

    def on_control_event(self, event: RemoteControlEvent) -> bytes:
        self.logger.debug('Event received: %s', event)
        if event:
            if event.get_code() == media_api.CODE_OK:
                pyautogui.press('enter')
            elif event.get_code() == media_api.CODE_LEFT:
                pyautogui.press('left')
            elif event.get_code() == media_api.CODE_RIGHT:
                pyautogui.press('right')
            elif event.get_code() == media_api.CODE_UP:
                pyautogui.press('up')
            elif event.get_code() == media_api.CODE_DOWN:
                pyautogui.press('down')
            elif event.get_code() == media_api.CODE_BACK:
                pyautogui.press('esc')
            elif event.get_code() == media_api.CODE_CH:
                value: str = event.get_data()
                if value.isnumeric():
                    self.__display_at_top(value)
            elif event.get_data():
                self.__display_at_center(event.get_data())
        return media_api.RESPONSE_ACK

    def on_stop(self) -> None:
        if self.__cnv_grid:
            self.__cnv_grid.clear()
