# -*- coding: utf-*-
# grid of images in a canvas object
import datetime
import logging
import threading
import time
import tkinter as tk
import traceback
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List
from id_threading_utils import Executor, Future
from PIL import Image, ImageDraw, ImageTk, ImageFont

DEFAULT_PADDING: int = 4
DEFAULT_CELL_WIDTH: int = 384
DEFAULT_CELL_HEIGHT: int = 216
DEFAULT_SELECTION_BORDER_WIDTH: int = 2
DEFAULT_SELECTION_BORDER_COLOR: str = 'white'
_AVAILABLE_CELLS: str = 'Available cells: '
_PREVENT_EVENT_PROPAGATION: str = 'break'
_ROW_OUT_OF_BOUNDS: str = 'Row is out of bounds: '
_UNEXPECTED_ERROR: str = 'Unexpected error: '


class PadKey(Enum):
    LEFT = 1
    RIGHT = 2
    UP = 3
    DOWN = 4
    DELETE = 5
    OK = 6


class ImageEntry(object):
    def __init__(self, tk_id: Any = None, image: Image = None, image_tk: ImageTk.PhotoImage = None):
        self.__tk_id: Any = tk_id
        self.__image: Image = image
        # PhotoImage must be referenced to avoid removal of its reference by the garbage collector
        self.__image_tk: ImageTk.PhotoImage = image_tk
        self.__updating: bool = False
        # noinspection PyTypeChecker
        self.__last_update: datetime.datetime = None

    def get_image(self) -> Image:
        return self.__image

    def get_image_tk(self) -> ImageTk.PhotoImage:
        return self.__image_tk

    def get_tk_id(self) -> Any:
        return self.__tk_id

    def is_updating(self) -> bool:
        return self.__updating

    def get_last_update(self) -> datetime.datetime:
        return self.__last_update

    def set_image(self, value: Image) -> None:
        self.__image = value

    def set_image_tk(self, value: ImageTk.PhotoImage) -> None:
        self.__image_tk = value

    def set_tk_id(self, value: Any) -> None:
        self.__tk_id = value

    def set_updating(self, flag: bool) -> None:
        self.__updating = flag

    def set_last_update(self, date: datetime.datetime) -> None:
        self.__last_update = date


class CanvasGridCell(object):
    def __init__(self, label: str = '', value: Any = None):
        self.__row: int = -1
        self.__column: int = -1
        self.__x: int = -1
        self.__y: int = -1
        self.__label: str = label
        self.__value: Any = value
        # noinspection PyTypeChecker
        self.__image_entry: ImageEntry = None

    def get_image_entry(self) -> ImageEntry:
        return self.__image_entry

    def get_label(self) -> str:
        return self.__label

    def get_row(self) -> int:
        return self.__row

    def get_column(self) -> int:
        return self.__column

    def get_x(self) -> int:
        return self.__x

    def get_y(self) -> int:
        return self.__y

    def get_value(self) -> Any:
        return self.__value

    def set_image_entry(self, value: ImageEntry) -> None:
        self.__image_entry = value

    def set_label(self, value: str) -> None:
        self.__label = value

    def set_value(self, value: Any) -> None:
        self.__value = value

    def set_coordinates(self, x: int, y: int) -> None:
        self.__x = x
        self.__y = y

    def set_row(self, value: int) -> None:
        self.__row = value

    def set_column(self, value: int) -> None:
        self.__column = value

    def __str__(self):
        return super().__str__() + ',' + str(self.__row) + ',' + str(self.__column) + ' ' + str(self.__x) + ',' + str(
            self.__y) + ': ' + self.__label


class CanvasGridListener(ABC):
    @abstractmethod
    def on_cell_validation(self, grid, cell: CanvasGridCell) -> None:
        pass

    @abstractmethod
    def on_cell_selection(self, grid, previous: CanvasGridCell, current: CanvasGridCell) -> None:
        pass


class DefaultCanvasGridListener(CanvasGridListener):
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger):
        if not DefaultCanvasGridListener.__logger:
            DefaultCanvasGridListener.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                DefaultCanvasGridListener.__logger.addHandler(handler)
            DefaultCanvasGridListener.__logger.setLevel(parent_logger.level)
        DefaultCanvasGridListener.__logger.info('Initializing %s', self.__class__.__name__)

    def on_cell_validation(self, grid, cell: CanvasGridCell) -> None:
        DefaultCanvasGridListener.__logger.debug('Cell validation: %s', cell)

    def on_cell_selection(self, grid, previous: CanvasGridCell, current: CanvasGridCell) -> None:
        DefaultCanvasGridListener.__logger.debug('Cell selection: %s', current)


class CanvasGridRenderer(ABC):
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger):
        if not CanvasGridRenderer.__logger:
            CanvasGridRenderer.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                CanvasGridRenderer.__logger.addHandler(handler)
            CanvasGridRenderer.__logger.setLevel(parent_logger.level)
        CanvasGridRenderer.__logger.info('Initializing %s', self.__class__.__name__)
        self.__font: ImageFont = ImageFont.load_default()
        self._background_color: str = 'black'
        self._border_color: str = 'lightgrey'

    @staticmethod
    def __add_corners(image: Image, rad) -> Image:
        circle = Image.new('L', (rad * 2, rad * 2), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, rad * 2, rad * 2), fill=255)
        alpha = Image.new('L', image.size, 255)
        w, h = image.size
        alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
        alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
        alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
        alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
        image.putalpha(alpha)
        return image

    def render_cell(self, grid, cell: CanvasGridCell, cell_width: int, cell_height: int, render_image: bool = True) -> None:
        CanvasGridRenderer.__logger.debug('Rendering cell: %s', cell)
        # noinspection PyBroadException
        try:
            image_entry: ImageEntry = cell.get_image_entry()
            if render_image or image_entry is None or image_entry.get_image() is None:
                image: Image = None
                if render_image:
                    CanvasGridRenderer.__logger.debug('Loading image for cell: %s', cell)
                    image = self.render_image(cell.get_value())
                # Create the cell background image
                result: Image = Image.new('RGB', (cell_width, cell_height), color=self._background_color)
                if image:
                    CanvasGridRenderer.__logger.debug('Centering image for cell: %s', cell)
                    # Resize image to fill the cell keeping the ration
                    image_w, image_h = image.size
                    CanvasGridRenderer.__logger.debug('Loaded image size: %sx%s', str(image_w), str(image_h))
                    if image_w > cell_width or image_h > cell_height:
                        image.thumbnail((cell_width, cell_width), Image.ANTIALIAS)
                        image_w, image_h = image.size
                        CanvasGridRenderer.__logger.debug('Resized image size: %sx%s', str(image_w), str(image_h))
                        # unused: image = image.crop((0, 0, cell_width, cell_height))
                    # Put the image on the center of the background image of the cell
                    image_w, image_h = image.size
                    CanvasGridRenderer.__logger.debug('Final image size: %sx%s', str(image_w), str(image_h))
                    cell_image_w, cell_image_h = result.size
                    CanvasGridRenderer.__logger.debug('Cell size: %sx%s', str(cell_image_w), str(cell_image_h))
                    result.paste(image, ((cell_image_w - image_w) // 2, (cell_image_h - image_h) // 2))
                else:
                    CanvasGridRenderer.__logger.warning('No image loaded for cell: %s', cell)
                draw: ImageDraw.Draw = ImageDraw.Draw(result)
                if cell.get_label():
                    draw.text((4, 4), cell.get_label(), (255, 255, 255), font=self.__font)
                    draw.text((4, 4), cell.get_label(), (255, 255, 255))
                draw.rounded_rectangle(((0, 0), (cell_width - 1, cell_height - 1)), radius=8,
                                       outline=self._border_color, width=1)
                # Round corners
                CanvasGridRenderer.__add_corners(result, 8)
                CanvasGridRenderer.__logger.debug('Cell image loaded: %s', cell)
            else:
                CanvasGridRenderer.__logger.debug('Cell image unchanged: %s', cell)
                result = image_entry.get_image()
            if result:
                CanvasGridRenderer.__logger.debug('Submitting canvas update for cell: %s', cell)
                grid.get_canvas().after(50, grid.update_cell_image, cell, result)
            else:
                cell.get_image_entry().set_last_update(datetime.datetime.now())
                cell.get_image_entry().set_updating(False)
                CanvasGridRenderer.__logger.debug('Invalid image to update on canvas for cell: %s', cell)
            CanvasGridRenderer.__logger.debug('Cell rendered: %s', cell)
        except:  # catch all
            CanvasGridRenderer.__logger.error(traceback.format_exc())

    @abstractmethod
    def render_image(self, value: Any) -> Image:
        pass


class DefaultCanvasGridRenderer(CanvasGridRenderer):
    def __init__(self, parent_logger: logging.Logger):
        super().__init__(parent_logger)

    def render_image(self, value: Any) -> Image:
        return None


CanvasGridCells = List[CanvasGridCell]
Images = Dict[int, ImageEntry]


class CanvasGrid(object):
    __logger: logging.Logger = None

    @staticmethod
    def __round_rectangle(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, r: int = 25, **kwargs) -> Any:
        points = (
            x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r, x2,
            y2,
            x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1,
            y1)
        return canvas.create_polygon(points, **kwargs, smooth=True, fill='')

    @staticmethod
    def free_image(canvas: tk.Canvas, cell: CanvasGridCell) -> None:
        entry: ImageEntry = cell.get_image_entry()
        # noinspection PyBroadException
        try:
            if entry:
                tk_id: Any = entry.get_tk_id()
                if tk_id and canvas.find_above(tk_id):
                    CanvasGrid.__logger.debug('Deleting canvas image')
                    canvas.delete(tk_id)
        except:  # catch all
            CanvasGrid.__logger.error(traceback.format_exc())
        finally:
            if entry:
                # PhotoImage reference can be processed by the garbage collector
                # noinspection PyTypeChecker
                entry.set_image_tk(None)
                # noinspection PyTypeChecker
                entry.set_tk_id(None)

    def __init__(self, parent_logger: logging.Logger, window: tk.Tk, canvas: tk.Canvas, executor: Executor):
        if not CanvasGrid.__logger:
            CanvasGrid.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                CanvasGrid.__logger.addHandler(handler)
            CanvasGrid.__logger.setLevel(parent_logger.level)
        CanvasGrid.__logger.info('Initializing %s', self.__class__.__name__)
        # Locks
        self.__cells_lock: threading.RLock = threading.RLock()
        self.__selection_lock: threading.RLock = threading.RLock()
        # Executor
        self.__executor: Executor = executor
        # Fields
        self.__padding: int = DEFAULT_PADDING
        self.__cell_width: int = DEFAULT_CELL_WIDTH
        self.__cell_height: int = DEFAULT_CELL_HEIGHT
        self.__window: tk.Tk = window
        self.__canvas: tk.Canvas = canvas
        self.__cells: CanvasGridCells = list()
        self.__parent_logger: logging.Logger = parent_logger
        self.__listener: CanvasGridListener = DefaultCanvasGridListener(parent_logger)
        self.__renderer: CanvasGridRenderer = DefaultCanvasGridRenderer(parent_logger)
        self.__first_visible_row: int = 0
        self.__selected_position: int = -1
        self.__selection_shape_id: Any = None
        self.__selection_border_width: int = DEFAULT_SELECTION_BORDER_WIDTH
        self.__selection_border_color: str = DEFAULT_SELECTION_BORDER_COLOR
        self.__window.bind('<Left>', lambda e: self.on_key(PadKey.LEFT))
        self.__window.bind('<Right>', lambda e: self.on_key(PadKey.RIGHT))
        self.__window.bind("<Up>", lambda e: self.on_key(PadKey.UP))
        self.__window.bind("<Down>", lambda e: self.on_key(PadKey.DOWN))
        self.__window.bind("<BackSpace>", lambda e: self.on_key(PadKey.DELETE))
        self.__window.bind('<Double-Button-1>', lambda e: self.on_key(PadKey.OK))
        self.__window.bind('<Return>', lambda e: self.on_key(PadKey.OK))
        self.__window.bind('<Button-1>', lambda e: self.__on_select(e))
        self.__rows: int = int(self.__canvas.winfo_height() / (self.__padding + self.__cell_height))
        self.__columns: int = int(self.__canvas.winfo_width() / (self.__padding + self.__cell_width))
        self.__margin_x: int = (self.__canvas.winfo_width() - (self.__padding + self.__cell_width) * self.__columns) / 2
        self.__margin_y: int = (self.__canvas.winfo_height() - (self.__padding + self.__cell_height) * self.__rows) / 2
        CanvasGrid.__logger.debug('Grid size: %sx%s', self.__columns, self.__rows)

    def get_canvas(self) -> tk.Canvas:
        return self.__canvas

    def get_cells(self) -> CanvasGridCells:
        with self.__cells_lock:
            return self.__cells

    def get_listener(self) -> CanvasGridListener:
        return self.__listener

    def set_listener(self, value: CanvasGridListener) -> None:
        if value is None:
            self.__listener = DefaultCanvasGridListener(self.__parent_logger)
        else:
            self.__listener = value

    def get_renderer(self) -> CanvasGridRenderer:
        return self.__renderer

    def set_renderer(self, value: CanvasGridRenderer) -> None:
        if value is None:
            self.__renderer = DefaultCanvasGridRenderer(self.__parent_logger)
        else:
            self.__renderer = value

    def get_padding(self) -> int:
        return self.__padding

    def set_padding(self, value: int) -> None:
        if 0 <= value <= 16:
            self.__padding = value

    def get_cell_width(self) -> int:
        return self.__cell_width

    def set_cell_width(self, value: int) -> None:
        if 16 < value <= 512:
            self.__cell_width = value

    def get_cell_height(self) -> int:
        return self.__cell_height

    def set_cell_height(self, value: int) -> None:
        if 16 < value <= 512:
            self.__cell_height = value

    def get_rows(self) -> int:
        return self.__rows

    def get_columns(self) -> int:
        return self.__columns

    def get_size(self) -> int:
        with self.__cells_lock:
            return len(self.__cells)

    def __get_cell(self, position: int) -> CanvasGridCell:
        with self.__cells_lock:
            if 0 <= position < len(self.__cells):
                return self.__cells[position]

    def get_tk(self) -> tk.Tk:
        return self.__window

    def update_cell_image(self, cell: CanvasGridCell, image):
        CanvasGrid.__logger.debug('Drawing cell: %s', cell)
        CanvasGrid.free_image(self.__canvas, cell)
        if not cell.get_image_entry():
            cell.set_image_entry(ImageEntry(image=image))
        else:
            cell.get_image_entry().set_image(image)
        entry: ImageEntry = cell.get_image_entry()
        if entry.get_image():
            image_tk: ImageTk.PhotoImage = ImageTk.PhotoImage(image=entry.get_image())
            # PhotoImage reference is kept to avoid removal by the garbage collector
            entry.set_image_tk(image_tk)
            with self.__selection_lock:
                entry.set_tk_id(self.__canvas.create_image(cell.get_x(), cell.get_y(), image=image_tk, anchor=tk.NW))
                # Select the cell if no cell is currently selected
                if self.get_selected_position() < 0:
                    self.__select_position(0)
            entry.set_last_update(datetime.datetime.now())
            entry.set_updating(False)
            CanvasGrid.__logger.debug('Cell image updated for cell: %s', cell)
        else:
            CanvasGrid.__logger.warning('No image for cell: %s', cell)
        # unused:if self.__window:
        # unused:    self.__canvas.after(50, self.__window.update)

    def redraw(self, cell: CanvasGridCell = None, first: int = -1) -> None:
        # Draw cell(s) on the new visible area
        cells_count: int = self.get_size()
        real_columns: int = min(cells_count, self.__columns)
        start: int = self.__first_visible_row * real_columns
        end: int = min(cells_count, start - 1 + self.__rows * real_columns)
        if cell:
            position: int = self.__cells.index(cell)
            if position >= 0 and start <= position <= end:
                start = position
                end = position
            else:
                CanvasGrid.__logger.debug('Redraw skipped, cell is outside the visible range of cells')
                return
        elif first >= 0 and start <= first <= end:
            start = first
        if start >= cells_count:
            CanvasGrid.__logger.warning('Redraw skipped, start argument is out of bound: %s', start)
            return
        if end < 0:
            end = cells_count
        CanvasGrid.__logger.debug('Drawing images from start: %s to %s', start, end)
        now: datetime.datetime = datetime.datetime.now()
        time_limit: datetime.datetime = now - datetime.timedelta(seconds=2)
        for position in range(start, end + 1):
            cell: CanvasGridCell = self.__get_cell(position)
            if not cell:
                CanvasGrid.__logger.debug('Redraw skipped, cell position is invalid: %s', position)
                continue
            if not cell.get_image_entry():
                cell.set_image_entry(ImageEntry())
            entry: ImageEntry = cell.get_image_entry()
            if entry.is_updating() or (entry.get_last_update() and entry.get_last_update() > time_limit):
                CanvasGrid.__logger.debug('Redraw skipped, cell updating or updated too recently: %s', cell)
                continue
            cell.set_row(int(position / self.__columns))
            cell.set_column(position % self.__columns)
            if cell.get_row() < self.__first_visible_row or cell.get_row() >= self.__first_visible_row + self.__rows:
                cell.set_coordinates(-self.__cell_width, -self.__cell_height)
                CanvasGrid.__logger.info('Redraw skipped, cell is outside the visible area: %s', cell)
                continue
            entry.set_updating(True)
            cell.set_coordinates(
                self.__margin_x + self.__padding + cell.get_column() * (self.__cell_width + self.__padding),
                self.__margin_y + self.__padding + (cell.get_row() - self.__first_visible_row) * (
                            self.__cell_height + self.__padding)
            )
            CanvasGrid.__logger.debug('Setting coordinates to: %s,%s for cell: %s', cell.get_x(), cell.get_y(), cell)
            if self.__window:
                self.__executor.submit(self.__renderer.render_cell, self, cell, self.__cell_width, self.__cell_height, True)

    def get_selected_cell(self) -> CanvasGridCell:
        with self.__selection_lock:
            if self.__selected_position >= 0:
                return self.__get_cell(self.__selected_position)

    def get_selected_position(self) -> int:
        with self.__selection_lock:
            return self.__selected_position

    def on_key(self, key: PadKey) -> None:
        CanvasGrid.__logger.debug('Key event: %s', key)
        cells_count: int = self.get_size()
        if cells_count == 0:
            return
        with self.__selection_lock:
            if key != PadKey.OK and self.__selected_position < 0:
                self.__select_position(0)
                return
            real_columns: int = min(cells_count, self.__columns)
            selected_cell: CanvasGridCell = self.__get_cell(self.__selected_position)
            last_row: int = int(cells_count / real_columns) - 1
            row: int = selected_cell.get_row()
            column: int = selected_cell.get_column()
            next_position: int = self.__selected_position
            CanvasGrid.__logger.debug('Current selected position: %s, row: %s', self.__selected_position, row)
            if key == PadKey.OK:
                CanvasGrid.__logger.debug('Opening cell at position: %s', self.__selected_position)
                self.__listener.on_cell_validation(self, selected_cell)
                return
            elif key == PadKey.DELETE:
                self.delete_cell(position=self.__selected_position)
                self.redraw(first=self.__selected_position)
                return
            elif key == PadKey.LEFT:
                if self.__selected_position == 0:
                    # Scroll to last row and select last cell
                    next_position = cells_count - 1
                    self.__scroll_to(last_row - self.__rows + 1)
                else:
                    # Select previous cell
                    next_position = self.__selected_position - 1
                    if self.__selected_position == self.__first_visible_row * real_columns:
                        # Scroll to previous row
                        self.__scroll_to(row - 1)
            elif key == PadKey.RIGHT:
                if self.__selected_position == cells_count - 1:
                    # Scroll to first row and select first cell
                    next_position = 0
                    self.__scroll_to(0)
                else:
                    # Select next cell
                    next_position = self.__selected_position + 1
                    if self.__selected_position == (self.__first_visible_row + self.__rows) * real_columns - 1:
                        # Scroll to next row and select next cell
                        self.__scroll_to(row + 1)
            elif key == PadKey.UP:
                if row == 0:
                    # Scroll to last row and select cell of last row on the same column
                    next_position = last_row * real_columns + column
                    self.__scroll_to(last_row - self.__rows + 1)
                else:
                    # Select cell of the previous row on the same column
                    next_position = (row - 1) * real_columns + column
                    if row == self.__first_visible_row:
                        # Scroll to previous row and select cell or previous row an the same column
                        self.__scroll_to(row - 1)
            elif key == PadKey.DOWN:
                if row == int(cells_count / real_columns) - 1:
                    # Scroll to first row and select cell of first row on the same column
                    next_position = column
                    self.__scroll_to(0)
                else:
                    # Select cell of the next row on the same column
                    next_position = (row + 1) * real_columns + column
                    if row == self.__first_visible_row + self.__rows - 1:
                        # Scroll to next row and select cell of next row on the same column
                        self.__scroll_to(row)
            if next_position == -1:
                CanvasGrid.__logger.debug('Code not handled by scroll action: %s', key)
            elif next_position != self.__selected_position:
                self.__select_position(next_position)

    # noinspection PyUnusedLocal
    def __delete_selection(self, event=None) -> None:
        with self.__selection_lock:
            CanvasGrid.__logger.debug('Clearing selection: %s', self.__selected_position)
            if self.__selection_shape_id:
                self.__canvas.delete(self.__selection_shape_id)
                self.__selection_shape_id = None

    def __on_select(self, event) -> None:
        with self.__selection_lock:
            x, y = event.x, event.y
            start: int = self.__first_visible_row * self.__columns
            end: int = min(start + (self.__rows * self.__columns), self.get_size())
            CanvasGrid.__logger.debug('Searching cell from: %s to %s', start, end)
            for p in range(start, end):
                cell: CanvasGridCell = self.__get_cell(p)
                if cell and cell.get_x() <= x <= cell.get_x() + self.__cell_width and cell.get_y() <= y <= cell.get_y() + self.__cell_height:
                    self.__select_position(p)
                    return

    def __index_of(self, cell: CanvasGridCell) -> int:
        try:
            return self.__cells.index(cell)
        except ValueError:
            return -1

    def select_cell(self, cell: CanvasGridCell) -> None:
        position: int = self.__index_of(cell)
        if position >= 0:
            self.__select_position(position)

    def __select_position(self, position: int) -> None:
        if position < 0 or position >= self.get_size():
            return
        cell: CanvasGridCell = self.__get_cell(position)
        if cell:
            with self.__selection_lock:
                if self.__selection_shape_id:
                    self.__canvas.delete(self.__selection_shape_id)
                    self.__selection_shape_id = None
                # noinspection PyTypeChecker
                previous_selected_cell: CanvasGridCell = None
                if self.__selected_position >= 0:
                    previous_selected_cell = self.__get_cell(self.__selected_position)
                CanvasGrid.__logger.debug('Selecting cell at position: %s/%s', position, self.get_size() - 1)
                self.__listener.on_cell_selection(self, previous_selected_cell, cell)
                self.__selected_position = position
                x: int = cell.get_x()
                y: int = cell.get_y()
                if x > 0 and y > 0:
                    self.__selection_shape_id = CanvasGrid.__round_rectangle(self.__canvas, x, y,
                                                                             x + self.__cell_width,
                                                                             y + self.__cell_height,
                                                                             width=self.__selection_border_width,
                                                                             outline=self.__selection_border_color)

    def __clear_row(self, row: int):
        if row < 0:
            CanvasGrid.__logger.debug(_ROW_OUT_OF_BOUNDS + str(row))
            return
        cells_count: int = self.get_size()
        real_columns: int = min(cells_count, self.__columns)
        first_position: int = row * real_columns
        last_row: int = int(cells_count / real_columns) - 1
        if row > last_row:
            CanvasGrid.__logger.debug(_ROW_OUT_OF_BOUNDS + str(row) + '/' + str(last_row))
            return
        last_visible_row: int = self.__first_visible_row + self.__rows - 1
        if row < self.__first_visible_row or row > last_visible_row:
            CanvasGrid.__logger.debug('Row is not visible: %s (%s,%s)', row, self.__first_visible_row, last_visible_row)
            return
        CanvasGrid.__logger.debug('Clearing cells of row: %s', row)
        # Delete images associated to the cells on the row and unbind events on cells
        if first_position <= self.get_selected_position() <= first_position + real_columns:
            self.__delete_selection()
        for position in range(first_position, first_position + real_columns):
            CanvasGrid.__logger.debug('Clearing cell at position: %s', position)
            CanvasGrid.free_image(self.__canvas, self.__cells[position])

    def __scroll_to(self, row: int) -> None:
        if row < 0:
            CanvasGrid.__logger.debug(_ROW_OUT_OF_BOUNDS + str(row))
            return
        cells_count: int = self.get_size()
        real_columns: int = min(cells_count, self.__columns)
        last_row: int = int(cells_count / real_columns) - 1
        if row > last_row:
            CanvasGrid.__logger.debug(_ROW_OUT_OF_BOUNDS + str(row) + '/' + str(last_row))
            return
        CanvasGrid.__logger.debug('Scrolling from first visible row: %s to %s', self.__first_visible_row, row)
        CanvasGrid.__logger.debug(_AVAILABLE_CELLS + str(cells_count))
        CanvasGrid.__logger.debug('Clearing rows')
        # Delete images associated to the visible cells and unbind events on cells
        for visible_row in range(self.__first_visible_row, self.__first_visible_row + self.__rows):
            if row <= visible_row <= row + self.__rows - 1:
                continue
            self.__clear_row(visible_row)
        self.__first_visible_row = row
        self.redraw()

    def delete_cell(self, position: int) -> CanvasGridCell:
        if 0 <= position < self.get_size():
            with self.__cells_lock:
                CanvasGrid.__logger.debug('Deleting cell at position: %s', position)
                cell: CanvasGridCell = self.__cells.pop(position)
            # Delete image associated to the cell and unbind events on cell
            CanvasGrid.free_image(self.__canvas, cell)
            if position == self.get_selected_position() and position >= self.get_size() - 1:
                self.__select_position(position - 1)
            CanvasGrid.__logger.debug(_AVAILABLE_CELLS + str(self.get_size()))
            self.redraw(first=position)
            return cell

    def clear(self):
        with self.__cells_lock:
            cells_count: int = len(self.__cells)
            while cells_count > 0:
                self.delete_cell(cells_count - 1)
                cells_count = cells_count - 1
            self.redraw()
            self.__window.update()

    def add_cell(self, position: int = -1, label: str = None, value: Any = None) -> CanvasGridCell:
        with self.__cells_lock:
            if position < 0:
                position = len(self.__cells)
                CanvasGrid.__logger.debug('Appending cell at last position: %s', position)
                self.__cells.append(CanvasGridCell())
            else:
                CanvasGrid.__logger.debug('Adding cell at specified position: %s', position)
                while len(self.__cells) <= position:
                    self.__cells.append(CanvasGridCell())
            CanvasGrid.__logger.debug(_AVAILABLE_CELLS + str(len(self.__cells)))
            cell: CanvasGridCell = self.__cells[position]
        if not label:
            label = 'Cell ' + str(position)
        cell.set_label(label)
        if value:
            cell.set_value(value)
        CanvasGrid.__logger.debug('Cell added: %s', cell)
        self.redraw(cell=cell)
        return cell
