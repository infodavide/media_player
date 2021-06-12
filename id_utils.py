# -*- coding: utf-*-
# utilities
import json


def is_json(value: str) -> object:
    """
    Check if given textual value is a valid JSON representation.
    :param value: the textual value
    :return: True if textual value is a valid JSON.
    """
    try:
        return json.loads(value)
    except ValueError:
        return None


def to_bool(value: str) -> bool:
    """
    Convert the given value to boolean
    :param value: the text
    :return: True if text is 'on', 'yes', 'true' or '1' (insensitive case)
    """
    lc = value.lower()
    return lc == 'on' or lc == 'yes' or lc == 'true' or lc == '1'


def del_none(d: dict) -> None:
    """
    Delete the entry having None as value from the dict.
    :param d: the dict object
    :return:
    """
    if d is None:
        return
    for key, value in list(d.items()):
        if value is None:
            del d[key]
        elif isinstance(value, dict):
            del_none(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    del_none(item)


class ObjectView(object):
    """
    Make an object with attributes associated to the entries of the given dict object.
    :param: d: the dict object
    """
    def __init__(self, d):
        self.__dict__ = d

    """
    Returns the string representation of the view
    :return: the textual representation
    """
    def __str__(self):
        return str(self.__dict__)
