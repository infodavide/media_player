# -*- coding: utf-*-
# Media player screen
import io
import logging
import media_api
import os
import screeninfo
import sys
import threading
import time
import traceback

if sys.version_info.major == 3:
    import tkinter as tk
    import tkinter.font as tkf
else:
    # noinspection PyUnresolvedReferences,PyPep8Naming
    import Tkinter as tk
    # noinspection PyUnresolvedReferences,PyPep8Naming
    import tkFont as tkf

from typing import Any, List
from media_player_config import MediaPlayerConfig
from media_api import RemoteControlEvent, MediaPlayerInterface, Media, MediaSource, ControllerListener
from canvas_grid import CanvasGrid, CanvasGridListener, CanvasGridCell, CanvasGridRenderer
from id_network_utils import find_ip_v4
from id_threading_utils import Executor
from id_tk import TkClock
from PIL import Image, ImageTk


_FULLSCREEN: str = 'fullscreen'


class MediaPlayerInterfaceImpl(MediaPlayerInterface, CanvasGridListener):
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, config: MediaPlayerConfig, executor: Executor):
        """
        Initialize the media player interface.
        :param parent_logger: the main logger
        :param config: the configuration object
        """
        super().__init__(config)
        if not MediaPlayerInterfaceImpl.__logger:
            MediaPlayerInterfaceImpl.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                MediaPlayerInterfaceImpl.__logger.addHandler(handler)
            MediaPlayerInterfaceImpl.__logger.setLevel(parent_logger.level)
        MediaPlayerInterfaceImpl.__logger.info('Initializing %s', self.__class__.__name__)
        # Status flags
        self.__active: bool = False
        self.__playing: bool = False
        # Locks
        self.__lock: threading.RLock = threading.RLock()
        self.__executor: Executor = executor
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
        self.__window.bind('<Escape>', lambda e: self.send_control_event(RemoteControlEvent(media_api.CODE_BACK), e))
        self.__window.bind('<KP_Add>', lambda e: self.send_control_event(RemoteControlEvent(media_api.CODE_VOL_UP), e))
        self.__window.bind('<KP_Subtract>', lambda e: self.send_control_event(RemoteControlEvent(media_api.CODE_VOL_DOWN), e))
        self.__window.bind('<Control-KP_Add>', lambda e: self.send_control_event(RemoteControlEvent(media_api.CODE_CH_UP), e))
        self.__window.bind('<Control-KP_Subtract>', lambda e: self.send_control_event(RemoteControlEvent(media_api.CODE_CH_DOWN), e))
        for k in range(10):
            v: str = str(k)
            self.__window.bind('<KP_%s>' % v, lambda e, data=v: self.send_control_event(RemoteControlEvent(code=media_api.CODE_CH, data=data), e))
            self.__window.bind('<Control-KP_%s>' % v, lambda e, data=v: self.send_control_event(RemoteControlEvent(code=media_api.CODE_VOL, data=data), e))
        self.__window.attributes('-topmost', True)
        self.__window.attributes('-' + _FULLSCREEN, self.__full_screen_state)
        self.__window.minsize(1027, 768)
        w, h = self.__window.winfo_screenwidth(), self.__window.winfo_screenheight()
        self.__window.maxsize(w, h)
        MediaPlayerInterfaceImpl.__logger.info('Screen size: %sx%s', w, h)
        fonts = list(tkf.families())
        fonts.sort()
        for f in fonts:
            print(f)
        self.__default_font_name: str = 'Courier'
        ipv4: str = find_ip_v4()
        if ipv4:
            self.__top_lbl: tk.Label = tk.Label(self.__window, text='Ready ('+ipv4+')', bg='black', fg='white')
        else:
            self.__top_lbl: tk.Label = tk.Label(self.__window, text='Ready', bg='black', fg='white')
        self.__top_lbl.config(font=(self.__default_font_name, 22))
        self.__top_lbl.pack(fill=tk.X, ipadx=4, padx=4, side=tk.TOP)
        self.__center_cnv: tk.Canvas = tk.Canvas(self.__window, bg='black', height=h - 110, width=w, borderwidth=0, highlightthickness=0)
        self.__center_cnv.pack(fill=tk.X, expand=tk.TRUE)
        self.__bottom_lbl: tk.Label = tk.Label(self.__window, text="Ready\n\n", bg='black', fg='orange', justify=tk.LEFT)
        self.__bottom_lbl.config(font=(self.__default_font_name, 16))
        self.__bottom_lbl.pack(ipadx=4, padx=4, anchor=tk.S, side=tk.LEFT)
        self.__clock: TkClock = TkClock(self.__window, seconds=False, colon=True)
        self.__clock.config(font=(self.__default_font_name, 16), bg='black', fg='orange')
        self.__clock.pack(ipadx=4, padx=4)
        with open(self._config.get_root_path() + os.sep + 'images' + os.sep + 'background.jpg', 'rb') as fp:
            image: Image = Image.open(io.BytesIO(fp.read()))
        image = image.resize((self.__center_cnv.winfo_width(), self.__center_cnv.winfo_height()), Image.ANTIALIAS)
        self.__center_image_id = self.__center_cnv.create_image(0, 0, image=ImageTk.PhotoImage(image), anchor=tk.NW)
        self.__window.update()
        self.__cnv_grid = CanvasGrid(MediaPlayerInterfaceImpl.__logger, self.__window, self.__center_cnv, executor)
        self.__cnv_grid.set_listener(self)
        self.__view: tk.Frame = tk.Frame(self.__window, bg="black", height=h, width=w, borderwidth=0, highlightthickness=0)
        self.__view['background'] = 'black'
        self.__view.bind('<Control-q>', lambda e: self.send_control_event(RemoteControlEvent(media_api.CODE_POWER), e))
        self.__view.bind('<Escape>', lambda e: self.send_control_event(RemoteControlEvent(media_api.CODE_BACK), e))
        self.__view.bind('<KP_Add>', lambda e: self.send_control_event(RemoteControlEvent(media_api.CODE_VOL_UP), e))
        self.__view.bind('<KP_Subtract>', lambda e: self.send_control_event(RemoteControlEvent(media_api.CODE_VOL_DOWN), e))
        self.__view.bind('<Control-KP_Add>', lambda e: self.send_control_event(RemoteControlEvent(media_api.CODE_CH_UP), e))
        self.__view.bind('<Control-KP_Subtract>', lambda e: self.send_control_event(RemoteControlEvent(media_api.CODE_CH_DOWN), e))
        for k in range(10):
            v: str = str(k)
            self.__view.bind('<KP_%s>' % v,
                             lambda e, data=v: self.send_control_event(RemoteControlEvent(code=media_api.CODE_CH, data=data), e))
            self.__view.bind('<Control-KP_%s>' % v,
                             lambda e, data=v: self.send_control_event(RemoteControlEvent(code=media_api.CODE_VOL, data=data), e))
        MediaPlayerInterfaceImpl.__logger.info('Media player interface configured')

    def send_control_event(self, control_event: RemoteControlEvent, event: Any = None) -> None:
        if control_event and isinstance(self._listener, ControllerListener):
            MediaPlayerInterfaceImpl.__logger.debug('Forwarding event to listener: %s', control_event)
            listener: ControllerListener = self._listener
            listener.on_control_event(control_event)

    def get_view(self) -> tk.Widget:
        return self.__view

    def get_view_handle(self) -> int:
        return self.__view.winfo_id()

    def get_view_height(self) -> int:
        return self.__view.winfo_height()

    def get_view_width(self) -> int:
        return self.__view.winfo_width()

    def set_grid_visible(self, flag: bool):
        if flag:
            self.__view.after(1, self.__view.place_forget())
        else:
            self.__view.after(1, lambda: self.__view.place(relx=0.5, rely=0.5, anchor=tk.CENTER))
        time.sleep(0.3)

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
            MediaPlayerInterfaceImpl.__logger.debug('Starting...')
            self.__active = True
            MediaPlayerInterfaceImpl.__logger.info('Opening window...')
            # noinspection PyBroadException
            try:
                MediaPlayerInterfaceImpl.__logger.info('Window opened')
                self.__top_lbl.place(rely=0.0, relx=1.0, x=0, y=0, anchor=tk.NE)
                self.__clock.place(rely=1.0, relx=1.0, x=0, y=0, anchor=tk.SE)
                self.__window.mainloop()
            except:  # catch all
                MediaPlayerInterfaceImpl.__logger.debug(traceback.format_exc())
            finally:
                MediaPlayerInterfaceImpl.__logger.info('Stopped')
                self.__window = None
                self.__active = False
                if self._listener:
                    self._listener.on_interface_stop()
                if self.__view:
                    self.__view.destroy()
                if self.__window:
                    self.__window.destroy()

    # noinspection PyUnusedLocal
    def stop(self, event: Any = None) -> None:
        """
        Stop the threads.
        :return:
        """
        with self.__lock:
            if not self.__active:
                return
            MediaPlayerInterfaceImpl.__logger.info('Stopping...')
            self.__active = False
            try:
                if self.__view:
                    self.__view.destroy()
                if self.__window:
                    self.__window.quit()
            except Exception as ex:
                MediaPlayerInterfaceImpl.__logger.error('Cannot stop interface: %s' % ex)
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=6, file=sys.stderr)
                MediaPlayerInterfaceImpl.__logger.error(ex)

    def restart(self):
        self.stop()
        time.sleep(1)
        self.start()

    # noinspection PyUnusedLocal
    def toggle_full_screen(self, event: Any = None):
        MediaPlayerInterfaceImpl.__logger.debug('Entering %s mode', _FULLSCREEN)
        self.__full_screen_state = not self.__full_screen_state
        self.__window.attributes('-' + _FULLSCREEN, self.__full_screen_state)

    # noinspection PyUnusedLocal
    def quit_full_screen(self, event: Any = None):
        MediaPlayerInterfaceImpl.__logger.debug('Exiting %s mode', _FULLSCREEN)
        self.__full_screen_state = False
        self.__window.attributes('-' + _FULLSCREEN, self.__full_screen_state)

    def set_playing(self, flag: bool):
        self.__playing = flag
        self.__clock.set_active(not flag)
        MediaPlayerInterfaceImpl.__logger.debug('Setting playing mode: %s', flag)

    def refresh(self) -> None:
        if not self.__playing:
            self.__cnv_grid.redraw()

    def __clear_text_at_top(self):
        MediaPlayerInterfaceImpl.__logger.debug('Clearing text at top')
        self.__top_lbl['text'] = ''
        self.__cleanup_top_task = None

    def __clear_text_at_center(self):
        MediaPlayerInterfaceImpl.__logger.debug('Clearing text at center')
        if self.__center_text_id:
            self.__center_cnv.delete(self.__center_text_id)

    def __display_at_top(self, text: str = None, color: str = None):
        if self.__cleanup_top_task and self.__cleanup_top_task.is_alive():
            self.__cleanup_top_task.cancel()
        if not self.__top_lbl:
            return
        if text:
            MediaPlayerInterfaceImpl.__logger.debug('Displaying text at top: %s', text)
            self.__top_lbl['text'] = text
            self.__executor.schedule(3, self.__clear_text_at_top)
        else:
            MediaPlayerInterfaceImpl.__logger.debug('Displaying empty text at top')
            self.__top_lbl['text'] = ''
        if color:
            self.__top_lbl.configure(foreground=color)

    def __display_at_bottom(self, text: str = None, color: str = None):
        if not self.__bottom_lbl:
            return
        if text:
            MediaPlayerInterfaceImpl.__logger.debug('Displaying text at bottom: %s', text)
            self.__bottom_lbl['text'] = text
        else:
            MediaPlayerInterfaceImpl.__logger.debug('Displaying empty text at bottom')
            self.__bottom_lbl['text'] = ''
        if color:
            self.__bottom_lbl.configure(foreground=color)

    def __display_at_center(self, text: str = None, color: str = None):
        self.__clear_text_at_center()
        if not self.__center_text_id:
            return
        if text:
            MediaPlayerInterfaceImpl.__logger.debug('Displaying text at center: %s', text)
            if color:
                self.__center_text_id = self.__center_cnv.create_text(0, 0, font="Courier 24 bold", text=text, tag='text', anchor=tk.NW, fill=color)
            else:
                self.__center_text_id = self.__center_cnv.create_text(0, 0, font="Courier 24 bold", text=text, tag='text', anchor=tk.NW, fill='white')
            text_coordinates = self.__center_cnv.bbox(self.__center_text_id)
            self.__center_cnv.move(self.__center_text_id, (self.__center_cnv.winfo_width() / 2) - ((text_coordinates[2] - text_coordinates[0]) / 2), 50)
        else:
            MediaPlayerInterfaceImpl.__logger.debug('Displaying empty text at center')
            self.__clear_text_at_center()

    def display_title(self, text: str) -> None:
        self.__display_at_bottom(text, 'white')

    def display_notice(self, text: str) -> None:
        self.__display_at_bottom(text, 'white')

    def display_warning(self, text: str) -> None:
        self.__display_at_bottom(text, 'yellow')

    def display_error(self, text: str) -> None:
        self.__display_at_bottom(text, 'red')

    def on_cell_validation(self, grid, cell: CanvasGridCell) -> None:
        if self._listener:
            self._listener.on_grid_validation(grid, cell.get_value())

    # noinspection PyUnusedLocal
    def on_cell_selection(self, grid, previous: CanvasGridCell, cell: CanvasGridCell) -> None:
        if self._listener:
            self._listener.on_grid_selection(grid, cell.get_value())

    def set_grid_cells(self, values: List) -> int:
        self.__cnv_grid.clear()
        for value in values:
            self.add_grid_cell(value)
        return self.__cnv_grid.get_rows() * self.__cnv_grid.get_columns()

    def add_grid_cell(self, value: Any, position: int = -1, render: bool = True) -> int:
        if len(self.__cnv_grid.get_cells()) == 0:
            if isinstance(value, MediaSource):
                self.__cell_type = MediaSource
            elif isinstance(value, Media):
                self.__cell_type = Media
        if isinstance(value, MediaSource):
            source: MediaSource = value
            self.__cnv_grid.add_cell(position=position, label=source.get_name(), value=source)
            return position
        if isinstance(value, Media):
            media: Media = value
            self.__cnv_grid.add_cell(position=position, label=media.get_name(), value=media)
            return position
        MediaPlayerInterfaceImpl.__logger.warning('Type of value not handled: %s', self.__cell_type)
        return -1
