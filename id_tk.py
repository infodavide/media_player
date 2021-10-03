# -*- coding: utf-*-
# utilities

import time
import tkinter

"""
Example tkinter Clock widget, counting seconds and minutes in realtime.
Functions just like a Label widget.
The Clock class has three functions:
__init__ creates the clock widget, which is just an ordinary label.
The tick() function rewrites the label every 200 milliseconds (5 times 
  each minute) to the current time. This updates the seconds.
The blink_colon() function rewrites the label every second, making the
  colon appear to blink every second.
The secret sauce is tkinter's .after command. When a function completes,
the .after command triggers another (or the same) function to run after
a specified delay. __init__ triggers tick(), then tick() keeps triggering
itself until stopped.
All that complexity is hidden from you. Simply treat the clock as another
label widget with a funny name. *It should automatically work.*
How to add the clock widget:
    tkinter.Label(parent, text="Foo").pack()      # A widget
    Clock(parent).widget.pack()                   # Just another widget 
    tkinter.Label(parent, text="Bar").pack()      # Yet another widget
How to start/stop the clock widget:
    You don't.
    If you create a Clock().widget, the clock will start.
    If you destroy the widget, the clock will also be destroyed.
    To hide/restore the clock, use .pack_forget() and re-.pack().
    The clock will keep running while hidden.
"""


class TkClock(tkinter.Label):
    """ Class that contains the clock widget and clock refresh """

    def __init__(self, parent=None, seconds: bool = True, colon: bool = False):
        """
        Create and place the clock widget into the parent element
        It's an ordinary Label element with two additional features.
        """
        tkinter.Label.__init__(self, parent)
        self.__active: bool = True
        self.display_seconds: bool = seconds
        if self.display_seconds:
            self.time = time.strftime('%H:%M:%S')
        else:
            self.time = time.strftime('%I:%M %p').lstrip('0')
        self.display_time: str = self.time
        self.configure(text=self.display_time)
        if colon:
            self.blink_colon()
        if self.display_seconds:
            self.after(200, self.tick)
        else:
            self.after(15000, self.tick)

    def set_active(self, flag: bool) -> None:
        self.__active = flag

    def is_active(self) -> bool:
        return self.__active

    def tick(self):
        """ Updates the display clock every 200 milliseconds """
        if self.__active:
            new_time: str = None
            if self.display_seconds:
                new_time = time.strftime('%H:%M:%S')
            else:
                new_time = time.strftime('%I:%M %p').lstrip('0')
            if new_time != self.time:
                self.time = new_time
                self.display_time = self.time
                self.config(text=self.display_time)
        if self.display_seconds:
            self.after(200, self.tick)
        else:
            self.after(15000, self.tick)

    def blink_colon(self):
        """ Blink the colon every second """
        if self.__active:
            if ':' in self.display_time:
                self.display_time = self.display_time.replace(':', ' ')
            else:
                self.display_time = self.display_time.replace(' ', ':', 1)
            self.config(text=self.display_time)
        self.after(1000, self.blink_colon)
